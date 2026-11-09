"""What matters right now for the signed-in user.

`GET /api/now?user_id=emma` returns (times are local conference time, minutes are whole minutes from now):

    {
      "now", "simulated": bool,                      # simulated: DEMO_NOW is set
      "on_now": [Session + going, short_title],     # running now, short ones first, full-day events last
      "on_now_total", "soon", "soon_total",         # unchanged (the Dashboard reads the totals)
      "food": next_food() result or null,           # unchanged
      "my_next": agenda item or null,               # unchanged
      "next": Item or null,                         # where to be next
      "then": Item or null,                         # the item after that, food breaks included
      "horizon_minutes": 120,
      "slots": [{"starts_at", "minutes_from_now", "food": bool,
                 "featured": Session + {going, friends, why, on_agenda} | null,
                 "others": [Session + going, ...]}, ...],
    }

    Item = {"id", "type": "session"|"meeting"|"food", "source": "agenda"|"food"|"for_you", "title", "full_title",
            "starts_at", "ends_at", "room", "with_name", "session_id", "all_day", "minutes_from_now", "why"}

`going` counts confirmed agenda sessions of all users (mostly generated sample attendees); `friends` are up to two
names of people the user knows (their meetings first, then their top Match results) who saved the session.

The choices are pure functions below, tested without Elasticsearch. The food logic is `next_food()` from
app/now.py; the agenda timeline and short titles come from My brief, for-you rules from Schedule, and the people
ranking from Match.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter
from opentelemetry import trace

from ..clock import now as clock_now
from ..config import settings
from ..es import es
from ..now import next_food
from .brief import _ranked_people, build_timeline, short_title
from .schedule import _knn, _profile, annotate

router = APIRouter(prefix="/api/now", tags=["now"])

SOON_MINUTES = 90
HORIZON_MINUTES = 120
MAX_FRIENDS = 2
FIELDS = [
    "title", "starts_at", "ends_at", "day", "minutes", "kind", "is_food", "track", "level",
    "projects", "room", "venue", "speaker_names", "companies",
]  # fmt: skip


# ---------- pure helpers ----------


def split_now(sessions: list[dict], now_iso: str, soon_iso: str) -> tuple[list[dict], list[dict]]:
    """Sessions on now (short ones first, full-day co-located events last) and sessions starting before `soon_iso`."""
    on = [s for s in sessions if s["starts_at"] <= now_iso < s["ends_at"] and not s.get("is_food")]
    on.sort(key=lambda s: (s.get("kind") == "colocated", s["ends_at"]))
    soon = [s for s in sessions if now_iso < s["starts_at"] <= soon_iso]
    return on, soon


def minutes_until(now_iso: str, iso: str) -> int:
    return int((datetime.fromisoformat(iso) - datetime.fromisoformat(now_iso)).total_seconds() // 60)


def _is_break(s: dict) -> bool:
    return bool(s.get("is_food")) or s.get("kind") == "break"


def _item(i: dict, now_iso: str, source: str, why: list[str] | None = None) -> dict:
    return {
        "id": i["id"],
        "type": i["type"],
        "source": source,
        "title": i["title"],
        "full_title": i.get("full_title") or i["title"],
        "starts_at": i["starts_at"],
        "ends_at": i["ends_at"],
        "room": i.get("room") or "",
        "with_name": i.get("with_name"),
        "session_id": i.get("session_id"),
        "all_day": bool(i.get("all_day")),
        "minutes_from_now": minutes_until(now_iso, i["starts_at"]),
        "why": why or [],
    }


def pick_next(timeline: list[dict], annotated: list[dict], now_iso: str) -> dict | None:
    """Where to be next: the first confirmed agenda item that has not started (a meeting counts until it ends).
    Without one, the best for-you session starting next (earliest start, then best fit)."""
    for i in timeline:
        if i["type"] == "food":
            continue
        if i["starts_at"] > now_iso or (i["type"] == "meeting" and i["ends_at"] > now_iso):
            return _item(i, now_iso, "agenda", ["on your agenda"])
    picks = [
        s
        for s in annotated
        if s.get("for_you") and s["starts_at"] > now_iso and not _is_break(s) and s.get("kind") != "registration"
    ]
    if not picks:
        return None
    best = min(picks, key=lambda s: (s["starts_at"], -s.get("fit", 0), s["id"]))
    item = {"id": best["id"], "type": "session", "title": short_title(best.get("title") or ""),
            "full_title": best.get("title") or "", "starts_at": best["starts_at"], "ends_at": best["ends_at"],
            "room": best.get("room"), "session_id": best["id"], "all_day": best.get("kind") == "colocated"}  # fmt: skip
    return _item(item, now_iso, "for_you", list(best.get("why") or []))


def pick_then(timeline: list[dict], nxt: dict | None, now_iso: str) -> dict | None:
    """The agenda item or food break after `nxt`, not yet started. Without `nxt`, the first one still to come."""
    after = nxt["starts_at"] if nxt else now_iso
    for i in timeline:
        if (nxt and i["id"] == nxt["id"]) or i["starts_at"] <= now_iso or i["starts_at"] < after:
            continue
        if nxt and i["starts_at"] == after and i.get("session_id") == nxt.get("session_id"):
            continue
        if i["type"] == "food":
            return _item(i, now_iso, "food")
        return _item(i, now_iso, "agenda", ["on your agenda"])
    return None


def group_slots(sessions: list[dict], now_iso: str, horizon_iso: str) -> list[tuple[str, bool, list[dict]]]:
    """Sessions starting after now and up to the horizon, grouped by start time. Breaks get their own group so
    they can be drawn as a quiet row; at the same start they come after the talks."""
    groups: dict[tuple[str, bool], list[dict]] = {}
    for s in sessions:
        if now_iso < s["starts_at"] <= horizon_iso and s.get("kind") != "registration":
            groups.setdefault((s["starts_at"], _is_break(s)), []).append(s)
    return [(start, food, groups[(start, food)]) for start, food in sorted(groups)]


def choose_featured(candidates: list[dict], going: dict[str, int]) -> tuple[dict | None, list[str]]:
    """The one session to show as a card in a slot, and why: the user's agenda, else the best for-you match, else
    the session most attendees saved. None when nothing qualifies (the slot is just a "+N more" line)."""
    pool = [s for s in candidates if not _is_break(s)]
    mine = [s for s in pool if s.get("on_agenda")]
    if mine:
        return mine[0], ["on your agenda"]
    fits = [s for s in pool if s.get("for_you")]
    if fits:
        best = min(fits, key=lambda s: (-s.get("fit", 0), -going.get(s["id"], 0), s["id"]))
        return best, list(best.get("why") or [])
    popular = [s for s in pool if going.get(s["id"], 0) > 0]
    if popular:
        return min(popular, key=lambda s: (-going[s["id"]], s["id"])), ["popular with attendees"]
    return None, []


def card(s: dict, going: dict[str, int]) -> dict:
    """A session as the page needs it: the listed fields, a short title and the going count."""
    out = {k: s.get(k) for k in FIELDS} | {"id": s["id"], "short_title": short_title(s.get("title") or "")}
    return out | {"going": going.get(s["id"], 0), "on_agenda": bool(s.get("on_agenda"))}


def build_slots(
    annotated: list[dict],
    going: dict[str, int],
    friends: dict[str, list[str]],
    now_iso: str,
    horizon_iso: str,
) -> list[dict]:
    slots = []
    for start, food, group in group_slots(annotated, now_iso, horizon_iso):
        featured, why = (None, []) if food else choose_featured(group, going)
        others = sorted((s for s in group if s is not featured), key=lambda s: (-going.get(s["id"], 0), s["id"]))
        slots.append(
            {
                "starts_at": start,
                "minutes_from_now": minutes_until(now_iso, start),
                "food": food,
                "featured": card(featured, going)
                | {"friends": friends.get(featured["id"], [])[:MAX_FRIENDS], "why": why}
                if featured
                else None,
                "others": [card(s, going) for s in others],
            }
        )
    return slots


def known_people(agenda: list[dict], ranked: list[dict], user_id: str) -> dict[str, str]:
    """People the user knows, in order: their meetings and requests (declined left out), then top Match results."""
    known: dict[str, str] = {}
    for a in agenda:
        if a.get("kind") == "meeting" and a.get("with_id") and a.get("status") in ("pending", "confirmed"):
            known.setdefault(a["with_id"], a.get("with_name") or a["with_id"])
    for p in ranked:
        known.setdefault(p["id"], p.get("name") or p["id"])
    known.pop(user_id, None)
    return known


def parse_going(aggs: dict, known: dict[str, str]) -> tuple[dict[str, int], dict[str, list[str]]]:
    """Going counts per session, and names of known people per session in the order of `known`."""
    going = {b["key"]: b["doc_count"] for b in aggs.get("going", {}).get("buckets", [])}
    rank = {pid: n for n, pid in enumerate(known)}
    friends: dict[str, list[str]] = {}
    for b in aggs.get("known", {}).get("sessions", {}).get("buckets", []):
        ids = sorted((u["key"] for u in b.get("users", {}).get("buckets", []) if u["key"] in rank), key=rank.get)
        friends[b["key"]] = [known[i] for i in ids]
    return going, friends


# ---------- Elasticsearch ----------


def _sessions(day: str) -> list[dict]:
    """The day's sessions with the description, which the for-you rules read (it is not sent to the browser)."""
    r = es.search(
        index=settings.idx_sessions,
        size=1000,
        source_includes=[*FIELDS, "description"],
        sort=[{"starts_at": "asc"}],
        query={"bool": {"filter": [{"term": {"day": day}}], "must_not": [{"term": {"kind": "registration"}}]}},
    )
    return [h["_source"] | {"id": h["_id"]} for h in r["hits"]["hits"]]


def _agenda(user_id: str, day: str) -> list[dict]:
    r = es.search(
        index=settings.idx_agenda,
        size=200,
        sort=[{"starts_at": "asc"}],
        query={"bool": {"filter": [{"term": {"user_id": user_id}}]}},
    )
    items = [h["_source"] | {"id": h["_id"]} for h in r["hits"]["hits"]]
    return [i for i in items if (i.get("starts_at") or "")[:10] == day]


def _going(session_ids: list[str], known: dict[str, str]) -> tuple[dict[str, int], dict[str, list[str]]]:
    """One aggregation over every user's saved sessions: counts per session, and which known people saved each."""
    if not session_ids:
        return {}, {}
    size = len(session_ids)
    confirmed = {"bool": {"filter": [{"term": {"kind": "session"}}, {"term": {"status": "confirmed"}}]}}
    r = es.search(
        index=settings.idx_agenda,
        size=0,
        query={"bool": {"filter": [confirmed, {"terms": {"session_id": session_ids}}]}},
        aggs={
            "going": {"terms": {"field": "session_id", "size": size}},
            "known": {
                "filter": {"terms": {"user_id": list(known)}},
                "aggs": {
                    "sessions": {
                        "terms": {"field": "session_id", "size": size},
                        "aggs": {"users": {"terms": {"field": "user_id", "size": 20}}},
                    }
                },
            },
        },
    )
    return parse_going(r.get("aggregations", {}), known)


def _strip(s: dict, going: dict[str, int]) -> dict:
    return {k: v for k, v in s.items() if k != "description"} | {
        "short_title": short_title(s.get("title") or ""),
        "going": going.get(s["id"], 0),
    }


def _lean_food(food: dict | None) -> dict | None:
    if not food:
        return None
    return food | {"session": {k: v for k, v in food["session"].items() if k != "description"}}


@router.get("")
def now_view(user_id: str | None = None) -> dict:
    current = clock_now()
    day = current.date().isoformat()
    now_iso = current.isoformat()
    soon_iso = (current + timedelta(minutes=SOON_MINUTES)).isoformat()
    horizon_iso = (current + timedelta(minutes=HORIZON_MINUTES)).isoformat()
    uid = user_id or settings.demo_user

    sessions = _sessions(day)
    on, soon = split_now(sessions, now_iso, soon_iso)
    agenda = _agenda(uid, day)
    profile, vector = _profile(uid)
    annotated = annotate(sessions, profile, agenda, _knn(day, vector) if vector else {})

    # Unchanged from before: the next confirmed agenda item today (the Dashboard reads it).
    upcoming = [a for a in agenda if a.get("status") == "confirmed" and a.get("ends_at", "") > now_iso]
    mine = next((a for a in upcoming if a.get("kind") == "meeting" or a["starts_at"] > now_iso), None)
    if mine:
        mine = {k: v for k, v in mine.items() if k != "id"}

    timeline = build_timeline(agenda, sessions, day)
    nxt = pick_next(timeline, annotated, now_iso)
    then = pick_then(timeline, nxt, now_iso)

    known = known_people(agenda, _ranked_people(uid, profile, vector) if profile else [], uid)
    in_window = [s["id"] for s in annotated if now_iso < s["starts_at"] <= horizon_iso and not _is_break(s)]
    going, friends = _going(sorted({*in_window, *(s["id"] for s in on)}), known)
    slots = build_slots(annotated, going, friends, now_iso, horizon_iso)

    span = trace.get_current_span()
    span.set_attribute("confox.now.on_now", len(on))
    span.set_attribute("confox.now.slots", len(slots))
    span.set_attribute("confox.now.next_source", nxt["source"] if nxt else "none")

    return {
        "now": now_iso,
        "simulated": bool(settings.demo_now),
        "on_now": [_strip(s, going) for s in on],
        "on_now_total": len(on),
        "soon": [{k: v for k, v in s.items() if k != "description"} for s in soon[:8]],
        "soon_total": len(soon),
        "food": _lean_food(next_food(sessions, current)),
        "my_next": mine,
        "next": nxt,
        "then": then,
        "horizon_minutes": HORIZON_MINUTES,
        "slots": slots,
    }
