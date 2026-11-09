"""My brief: one page for the signed-in attendee's day.

`GET /api/brief?user_id=emma` (day = the day of `clock.now()`) returns:

    {
      "now": "2026-11-09T08:40:00", "day": "2026-11-09",
      "user": {"id", "name", "first_name", "title", "company", "school", "interests"},
      "summary": "Your day centres on Cloud Native AI + Inference Day from 09:00. Coffee with Alice ...",
      "timeline": [{"id", "type": "session"|"meeting"|"food", "title", "full_title", "starts_at", "ends_at", "room",
                    "with_id", "with_name", "session_id", "status", "all_day", "is_next"}, ...],
      "gaps": [{"starts_at", "ends_at", "minutes"}, ...],      # free windows of 60+ minutes, 08:00-19:00, from now on
      "requests": {"incoming": [...], "outgoing": [...]},      # pending meetings today
      "people": [{"id", "name", "title", "company", "kind", "sample", "reason", "free_at"}, ...],   # up to 3
      "suggested": [Session + why/fit, ...],                   # up to 3 for-you sessions not on the agenda, not started
      "food": next_food() result or null,
    }

Everything here is assembled from other features: the day's sessions and for-you rules come from the schedule
router, the people ranking from the Match router, the food break from `app.now.next_food`. The merging, `is_next`,
gaps and summary are pure functions below, tested without Elasticsearch.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Query
from opentelemetry import trace

from ..clock import now as clock_now
from ..config import settings
from ..es import es
from ..now import next_food
from .people import _load_user, rank_people, why
from .schedule import _day_sessions, _knn, annotate

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/brief", tags=["brief"])

DAY_START = "08:00:00"
DAY_END = "19:00:00"
MIN_GAP_MINUTES = 60
MAX_PEOPLE = 3
MAX_SUGGESTED = 3
PEOPLE_CANDIDATES = 15


# ---------- pure helpers ----------


def short_title(title: str) -> str:
    """Drop the host and pass notes the schedule packs into titles: "Cloud Native AI + Inference Day Hosted by
    CNCF - Full Day Event | ALL ACCESS PASS REQUIRED" becomes "Cloud Native AI + Inference Day"."""
    title = (title or "").split(" | ")[0]
    return title.split(" Hosted by ")[0].strip()


def _minutes(start: str, end: str) -> int:
    return int((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() // 60)


def _overlaps(a: dict, b: dict) -> bool:
    return a["starts_at"] < b["ends_at"] and b["starts_at"] < a["ends_at"]


def build_timeline(agenda: list[dict], sessions: list[dict], day: str) -> list[dict]:
    """Today's confirmed agenda sessions and meetings, plus the day's food breaks, sorted by start.

    A food break that starts with a confirmed meeting is left out: the meeting already is that coffee. `all_day`
    marks co-located events, which do not block other plans (you drop in and out of them).
    """
    kind_by_id = {s["id"]: s.get("kind") for s in sessions}
    items: list[dict] = []
    for a in agenda:
        if a.get("status") != "confirmed" or (a.get("starts_at") or "")[:10] != day:
            continue
        is_meeting = a.get("kind") == "meeting"
        items.append(
            {
                "id": a["id"],
                "type": "meeting" if is_meeting else "session",
                "title": (a.get("title") if is_meeting else short_title(a.get("title") or ""))
                or ("Meeting" if is_meeting else "Session"),
                "full_title": a.get("title") or "",
                "starts_at": a["starts_at"],
                "ends_at": a["ends_at"],
                "room": a.get("room") or "",
                "with_id": a.get("with_id"),
                "with_name": a.get("with_name"),
                "session_id": a.get("session_id"),
                "status": "confirmed",
                "all_day": kind_by_id.get(a.get("session_id") or "") == "colocated",
            }
        )
    meeting_starts = {i["starts_at"] for i in items if i["type"] == "meeting"}
    for s in sessions:
        if not s.get("is_food") or s.get("day", s["starts_at"][:10]) != day or s["starts_at"] in meeting_starts:
            continue
        items.append(
            {
                "id": s["id"],
                "type": "food",
                "title": s.get("title") or "Break",
                "full_title": s.get("title") or "",
                "starts_at": s["starts_at"],
                "ends_at": s["ends_at"],
                "room": s.get("room") or "",
                "with_id": None,
                "with_name": None,
                "session_id": s["id"],
                "status": "open",
                "all_day": False,
            }
        )
    order = {"session": 0, "meeting": 1, "food": 2}
    items.sort(key=lambda i: (i["starts_at"], i["ends_at"], order[i["type"]]))
    return items


def mark_next(items: list[dict], now_iso: str) -> list[dict]:
    """Set `is_next` on the first item that has not ended. An all-day event already under way is skipped when
    something else is still to come, so the brief points at the next thing that needs you."""
    for i in items:
        i["is_next"] = False
    open_items = [i for i in items if i["ends_at"] > now_iso]
    focus = [i for i in open_items if not (i.get("all_day") and i["starts_at"] <= now_iso)]
    target = (focus or open_items or [None])[0]
    if target is not None:
        target["is_next"] = True
    return items


def find_gaps(items: list[dict], day: str, now_iso: str, min_minutes: int = MIN_GAP_MINUTES) -> list[dict]:
    """Free windows of at least `min_minutes` between 08:00 and 19:00 (from now on, if today has begun), not
    covered by any item. All-day events do not block: they would hide every gap."""
    start, end = f"{day}T{DAY_START}", f"{day}T{DAY_END}"
    cursor = max(start, now_iso) if now_iso[:10] == day else start
    blocks = sorted((i["starts_at"], i["ends_at"]) for i in items if not i.get("all_day"))
    gaps = []
    for b_start, b_end in [*blocks, (end, end)]:
        b_start, b_end = max(b_start, cursor), min(b_end, end)
        if b_start > cursor and _minutes(cursor, b_start) >= min_minutes:
            gaps.append({"starts_at": cursor, "ends_at": b_start, "minutes": _minutes(cursor, b_start)})
        cursor = max(cursor, b_end)
        if cursor >= end:
            break
    return gaps


def split_requests(agenda: list[dict], day: str, sessions: list[dict]) -> dict[str, list[dict]]:
    """Pending meetings today, split by direction (no direction means someone asked the user). A request without
    a room borrows the room of a food break starting at the same time, where the meeting would happen."""
    food_rooms = {s["starts_at"]: s.get("room") for s in sessions if s.get("is_food")}
    out: dict[str, list[dict]] = {"incoming": [], "outgoing": []}
    for a in agenda:
        if a.get("kind") != "meeting" or a.get("status") != "pending" or (a.get("starts_at") or "")[:10] != day:
            continue
        direction = a.get("direction") or "incoming"
        item = {
            "id": a["id"],
            "with_id": a.get("with_id"),
            "with_name": a.get("with_name") or "Someone",
            "title": a.get("title") or "Meeting",
            "starts_at": a["starts_at"],
            "ends_at": a.get("ends_at") or a["starts_at"],
            "room": a.get("room") or food_rooms.get(a["starts_at"]) or "",
            "message": a.get("message") or "",
            "session_id": a.get("session_id"),
            "direction": direction,
        }
        out["outgoing" if direction == "outgoing" else "incoming"].append(item)
    for v in out.values():
        v.sort(key=lambda i: i["starts_at"])
    return out


def free_food(sessions: list[dict], items: list[dict], now_iso: str, day: str) -> dict | None:
    """The first food break today, after now, that does not overlap the user's confirmed plans (all-day events
    excluded). That is when the user is free to meet someone."""
    busy = [i for i in items if i["type"] != "food" and not i.get("all_day")]
    for s in sorted(sessions, key=lambda s: s["starts_at"]):
        if not s.get("is_food") or s["starts_at"][:10] != day or s["starts_at"] <= now_iso:
            continue
        if any(_overlaps(s, b) for b in busy):
            continue
        return {"starts_at": s["starts_at"], "ends_at": s["ends_at"], "title": s.get("title") or "Break",
                "room": s.get("room") or ""}  # fmt: skip
    return None


def _hhmm(iso: str) -> str:
    return iso[11:16]


def build_summary(items: list[dict], requests: dict[str, list[dict]], now_iso: str) -> str:
    """One or a few plain sentences built from the data, no LLM."""
    parts: list[str] = []
    upcoming = [i for i in items if i["ends_at"] > now_iso]
    anchor = next((i for i in upcoming if i["type"] == "session" and i.get("all_day")), None)
    sessions = [i for i in upcoming if i["type"] == "session"]
    if anchor:
        parts.append(f"Your day centres on {short_title(anchor['title'])} from {_hhmm(anchor['starts_at'])}.")
    elif sessions:
        first = sessions[0]
        n = len(sessions)
        lead = "1 session" if n == 1 else f"{n} sessions"
        parts.append(f"You have {lead} left today, starting with {short_title(first['title'])} at "
                     f"{_hhmm(first['starts_at'])}.")  # fmt: skip
    meetings = [f"{i['title']} with {i['with_name'] or 'someone'} at {_hhmm(i['starts_at'])}"
                for i in upcoming if i["type"] == "meeting"]  # fmt: skip
    if meetings:
        joined = meetings[0] if len(meetings) == 1 else ", ".join(meetings[:-1]) + " and " + meetings[-1]
        parts.append(joined[0].upper() + joined[1:] + ".")
    n_in = len(requests.get("incoming", []))
    if n_in:
        parts.append("1 meeting request is waiting for you." if n_in == 1
                     else f"{n_in} meeting requests are waiting for you.")  # fmt: skip
    n_out = len(requests.get("outgoing", []))
    if n_out:
        parts.append("You are waiting on 1 reply." if n_out == 1 else f"You are waiting on {n_out} replies.")
    if not parts:
        parts.append("Nothing is planned for the rest of today yet.")
    return " ".join(parts)


def pick_suggested(annotated: list[dict], now_iso: str, limit: int = MAX_SUGGESTED) -> list[dict]:
    """For-you sessions that match the user's interests, are not on the agenda, have not started and do not
    clash. Breaks, keynote-only picks and other co-located days (they would replace the user's own) are left out."""
    picks = [
        s
        for s in annotated
        if s.get("for_you")
        and not s.get("on_agenda")
        and not s.get("clashes")
        and not s.get("is_food")
        and s.get("kind") not in ("colocated", "break", "registration")
        and s["starts_at"] > now_iso
        and any(w.startswith("matches") or w == "close to your interests" for w in s.get("why") or [])
    ]
    picks.sort(key=lambda s: (-s.get("fit", 0), s["starts_at"]))
    return sorted(picks[:limit], key=lambda s: s["starts_at"])


def pick_people(user: dict, ranked: list[dict], skip_ids: set[str], free_at: dict | None) -> list[dict]:
    """Top matches with one short reason each, minus people the user already meets (or has a request with)."""
    out = []
    for p in ranked:
        if p["id"] in skip_ids:
            continue
        reasons = why(user, p)
        out.append(
            {
                "id": p["id"],
                "name": p.get("name") or p["id"],
                "title": p.get("title") or "",
                "company": p.get("company") or "",
                "kind": p.get("kind") or "",
                "sample": bool(p.get("sample")),
                "reason": reasons[0]["label"] if reasons else "",
                "free_at": free_at,
            }
        )
        if len(out) == MAX_PEOPLE:
            break
    return out


def user_card(user_id: str, user: dict) -> dict:
    name = user.get("name") or user_id
    schools = user.get("schools") or []
    return {
        "id": user_id,
        "name": name,
        "first_name": name.split()[0],
        "title": user.get("title") or "",
        "company": user.get("company") or "",
        "school": schools[0] if schools else "",
        "interests": user.get("interests") or [],
    }


# ---------- Elasticsearch ----------


def _agenda(user_id: str) -> list[dict]:
    r = es.search(
        index=settings.idx_agenda,
        query={"bool": {"filter": [{"term": {"user_id": user_id}}]}},
        sort=[{"starts_at": "asc"}],
        size=500,
    )
    return [h["_source"] | {"id": h["_id"]} for h in r["hits"]["hits"]]


def _ranked_people(user_id: str, user: dict, vector: list | None) -> list[dict]:
    """The Match ranking for the current profile (same pipeline as /api/people/match), best first."""
    ranked, _, mode = rank_people(user_id, user, vector, size=PEOPLE_CANDIDATES)
    trace.get_current_span().set_attribute("confox.brief.people_mode", mode)
    return ranked


@router.get("")
def brief(user_id: str = Query(default_factory=lambda: settings.demo_user)) -> dict:
    current = clock_now()
    now_iso = current.isoformat()
    day = current.date().isoformat()

    user, vector = _load_user(user_id)
    sessions = _day_sessions(day)
    agenda = _agenda(user_id)
    today = [a for a in agenda if (a.get("starts_at") or "")[:10] == day]

    items = mark_next(build_timeline(today, sessions, day), now_iso)
    gaps = find_gaps(items, day, now_iso)
    requests = split_requests(today, day, sessions)

    # Anyone the user already meets, has a request with, or declined today is not suggested again.
    known = {a["with_id"] for a in today if a.get("kind") == "meeting" and a.get("with_id")}
    people = pick_people(user, _ranked_people(user_id, user, vector), known | {user_id},
                         free_food(sessions, items, now_iso, day))  # fmt: skip

    knn_scores = _knn(day, vector) if vector else {}
    suggested = pick_suggested(annotate(sessions, user, today, knn_scores), now_iso)

    span = trace.get_current_span()
    span.set_attribute("confox.brief.timeline", len(items))
    span.set_attribute("confox.brief.requests_incoming", len(requests["incoming"]))
    span.set_attribute("confox.brief.people", len(people))
    span.set_attribute("confox.brief.suggested", len(suggested))

    return {
        "now": now_iso,
        "day": day,
        "user": user_card(user_id, user),
        "summary": build_summary(items, requests, now_iso),
        "timeline": items,
        "gaps": gaps,
        "requests": requests,
        "people": people,
        "suggested": suggested,
        "food": next_food(sessions, current),
        "sample": True,
    }
