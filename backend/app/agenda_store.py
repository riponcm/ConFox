"""The personal agenda: sessions a user added and meetings with other people, all in `confox-agenda`.

One document per item:

    { user_id, kind: "session" | "meeting", status: "confirmed" | "pending" | "declined",
      direction: "incoming" | "outgoing"   (meetings only; a pending meeting without one is incoming),
      session_id   (sessions: the session; meetings: the food or coffee break used as the slot, may be absent),
      with_id, with_name (meetings), title, starts_at, ends_at, room, message, sample, created_at }

Ids: an added session is "{user_id}-s-{session_id}", a new meeting request "{user_id}-m-{8 hex}". Seeded items keep
their own ids. The rules below are pure functions so they are tested without Elasticsearch; the few Elasticsearch
helpers at the end are shared by the agenda and connect routers.
"""

import re
import secrets
from datetime import datetime, timedelta

from elasticsearch import NotFoundError

from .clock import now
from .config import settings
from .es import es

MESSAGE_CHARS = 200
MAX_SLOTS = 3
ACTIVE = ("pending", "confirmed")


# ---------- pure rules ----------


def stamp(at: datetime | None = None) -> str:
    """Local time in the index's date format (seconds, no fraction, no offset)."""
    return (at or now()).replace(microsecond=0).isoformat()


def session_doc_id(user_id: str, session_id: str) -> str:
    return f"{user_id}-s-{session_id}"


def meeting_doc_id(user_id: str) -> str:
    return f"{user_id}-m-{secrets.token_hex(4)}"


def session_item(user_id: str, session: dict, at: datetime | None = None) -> dict:
    """The agenda document for a session the user chose. `session` needs an `id`."""
    return {
        "user_id": user_id,
        "kind": "session",
        "status": "confirmed",
        "session_id": session["id"],
        "title": session.get("title") or "Session",
        "starts_at": session["starts_at"],
        "ends_at": session["ends_at"],
        "room": session.get("room"),
        "sample": False,
        "created_at": stamp(at),
    }


def meeting_title(break_title: str) -> str:
    """ "Lunch | On Own" -> "Lunch", "Coffee Break" -> "Coffee"."""
    text = (break_title or "").lower()
    if "lunch" in text:
        return "Lunch"
    if "breakfast" in text:
        return "Breakfast"
    if "coffee" in text:
        return "Coffee"
    return re.split(r"\s*\|\s*", break_title or "Meeting")[0].strip() or "Meeting"


def trim_message(message: str | None) -> str:
    return " ".join((message or "").split())[:MESSAGE_CHARS]


def meeting_request(
    user_id: str, slot: dict, person: dict, message: str | None, at: datetime | None = None, request_id: str = ""
) -> dict:
    """A pending outgoing meeting at a food or coffee break. `slot` is a break session with `id`."""
    return {
        "request_id": request_id,
        "user_id": user_id,
        "kind": "meeting",
        "status": "pending",
        "direction": "outgoing",
        "session_id": slot["id"],
        "with_id": person["id"],
        "with_name": person.get("name") or person["id"],
        "title": meeting_title(slot.get("title", "")),
        "starts_at": slot["starts_at"],
        "ends_at": slot["ends_at"],
        "room": slot.get("room"),
        "message": trim_message(message),
        "sample": False,
        "created_at": stamp(at),
    }


def mirror_request(request: dict, sender: dict) -> dict:
    """The same request as the recipient sees it: theirs, incoming, from the sender."""
    return request | {
        "user_id": request["with_id"],
        "direction": "incoming",
        "with_id": sender["id"],
        "with_name": sender.get("name") or sender["id"],
    }


def direction(item: dict) -> str:
    """Pending meetings without a direction are requests someone sent the user (the seeded lunch request)."""
    return item.get("direction") or "incoming"


def overlaps(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    """Times are ISO strings in one local zone, so string order is time order."""
    return a_start < b_end and b_start < a_end


def split_agenda(items: list[dict]) -> dict:
    """GET /api/agenda: confirmed sessions and meetings in time order, plus pending meetings. Declined are left out."""
    by_time = sorted(items, key=lambda i: (i.get("starts_at") or "", i.get("ends_at") or ""))
    return {
        "items": [i for i in by_time if i.get("status") == "confirmed"],
        "pending": [i for i in by_time if i.get("kind") == "meeting" and i.get("status") == "pending"],
    }


def split_connect(items: list[dict]) -> dict:
    """GET /api/connect: pending requests to the user, pending requests from the user, confirmed meetings."""
    meetings = sorted(
        (i for i in items if i.get("kind") == "meeting"), key=lambda i: (i.get("starts_at") or "", i.get("id") or "")
    )
    pending = [m for m in meetings if m.get("status") == "pending"]
    return {
        "incoming": [m for m in pending if direction(m) == "incoming"],
        "outgoing": [m for m in pending if direction(m) == "outgoing"],
        "meetings": [m for m in meetings if m.get("status") == "confirmed"],
    }


def blocking(items: list[dict], kind_by_session: dict[str, str]) -> list[dict]:
    """Confirmed items that take the user's time. A full-day co-located event is left out, as in Schedule."""
    return [
        i
        for i in items
        if i.get("status") == "confirmed" and kind_by_session.get(i.get("session_id") or "") != "colocated"
    ]


def meetings_with(items: list[dict], with_id: str) -> list[dict]:
    """Pending or confirmed meetings with one person."""
    return [
        i for i in items if i.get("kind") == "meeting" and i.get("with_id") == with_id and i.get("status") in ACTIVE
    ]


def free_slots(
    food: list[dict],
    items: list[dict],
    kind_by_session: dict[str, str],
    with_id: str,
    at: datetime,
    limit: int = MAX_SLOTS,
    other_items: list[dict] | None = None,
) -> list[dict]:
    """Food and coffee breaks both people could meet at, earliest first: today from `at` on, then the next day
    with breaks. A break is taken when it overlaps a confirmed item of the user (co-located days aside) or a
    pending or confirmed meeting with the same person, or a confirmed item of the other person (`other_items`).
    `food` are `is_food` sessions with `id`."""
    now_iso = stamp(at)
    today = at.date().isoformat()
    upcoming = sorted(
        (f for f in food if f.get("starts_at") and f["starts_at"] >= now_iso),
        key=lambda f: (f["starts_at"], f.get("id") or ""),
    )
    later_days = sorted({f["starts_at"][:10] for f in upcoming if f["starts_at"][:10] > today})
    days = {today, *later_days[:1]}
    taken = (
        blocking(items, kind_by_session) + meetings_with(items, with_id) + blocking(other_items or [], kind_by_session)
    )
    slots = []
    for f in upcoming:
        if f["starts_at"][:10] not in days:
            continue
        if any(overlaps(f["starts_at"], f["ends_at"], t["starts_at"], t["ends_at"]) for t in taken):
            continue
        slots.append(
            {
                "session_id": f["id"],
                "title": meeting_title(f.get("title", "")),
                "starts_at": f["starts_at"],
                "ends_at": f["ends_at"],
                "room": f.get("room"),
                "day": f["starts_at"][:10],
            }
        )
        if len(slots) == limit:
            break
    return slots


def clashing_meeting(items: list[dict], with_id: str, starts_at: str, ends_at: str) -> dict | None:
    """An existing pending or confirmed meeting with this person at this time, if any."""
    return next(
        (m for m in meetings_with(items, with_id) if overlaps(starts_at, ends_at, m["starts_at"], m["ends_at"])), None
    )


# ---------- Elasticsearch ----------


def _hit(hit: dict) -> dict:
    return hit["_source"] | {"id": hit["_id"]}


def user_items(user_id: str, day: str | None = None) -> list[dict]:
    """Every agenda document of the user, optionally only those starting on `day` (YYYY-MM-DD)."""
    filters: list[dict] = [{"term": {"user_id": user_id}}]
    if day:
        start = datetime.fromisoformat(day)
        filters.append({"range": {"starts_at": {"gte": stamp(start), "lt": stamp(start + timedelta(days=1))}}})
    r = es.search(
        index=settings.idx_agenda,
        query={"bool": {"filter": filters}},
        sort=[{"starts_at": "asc"}],
        size=1000,
    )
    return [_hit(h) for h in r["hits"]["hits"]]


def linked_items(request_id: str) -> list[dict]:
    """Both sides of one meeting request."""
    if not request_id:
        return []
    r = es.search(index=settings.idx_agenda, query={"term": {"request_id": request_id}}, size=10)
    return [_hit(h) for h in r["hits"]["hits"]]


def get_item(item_id: str) -> dict | None:
    try:
        return _hit(es.get(index=settings.idx_agenda, id=item_id))
    except NotFoundError:
        return None


def session_kinds(session_ids: list[str]) -> dict[str, str]:
    """Kind per session id, for telling a co-located day from a normal slot."""
    ids = sorted({s for s in session_ids if s})
    if not ids:
        return {}
    r = es.mget(index=settings.idx_sessions, ids=ids, source_includes=["kind"])
    return {d["_id"]: d["_source"].get("kind", "") for d in r["docs"] if d.get("found")}


def get_session(session_id: str) -> dict | None:
    try:
        return _hit(es.get(index=settings.idx_sessions, id=session_id, source_excludes=["embedding"]))
    except NotFoundError:
        return None


def refresh() -> None:
    """After every write, so the next read (often the same click) sees it."""
    es.indices.refresh(index=settings.idx_agenda)
