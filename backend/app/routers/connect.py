"""Meet: ask someone to meet at a food or coffee break, and answer the requests others sent.

Meetings are agenda documents (kind "meeting") in `confox-agenda`; see app/agenda_store.py for the shape and the
slot rules. A request the user sends is `pending` + `outgoing`; one they receive is `pending` + `incoming` (or no
direction, like the seeded lunch request) until they accept (`confirmed`) or decline (`declined`).
"""

import logging

from elasticsearch import NotFoundError
from fastapi import APIRouter, HTTPException, Query
from opentelemetry import metrics, trace
from pydantic import BaseModel, Field

from .. import agenda_store as store
from ..clock import now
from ..config import settings
from ..es import es

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/connect", tags=["connect"])
requests = metrics.get_meter("confox.connect").create_counter(
    "confox.connect.requests", unit="{request}", description="Meeting requests sent, accepted or declined"
)


class SendRequest(BaseModel):
    user_id: str = Field(default_factory=lambda: settings.demo_user, min_length=1)
    with_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    message: str = ""


def _person(person_id: str) -> dict:
    try:
        doc = es.get(index=settings.idx_people, id=person_id, source_includes=["name", "kind"])
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"unknown person {person_id}") from exc
    return doc["_source"] | {"id": doc["_id"]}


def _food_sessions() -> list[dict]:
    """Food and coffee breaks from the start of today on."""
    today = now().date().isoformat()
    r = es.search(
        index=settings.idx_sessions,
        query={"bool": {"filter": [{"term": {"is_food": True}}, {"range": {"day": {"gte": today}}}]}},
        sort=[{"starts_at": "asc"}],
        source_includes=["title", "starts_at", "ends_at", "room", "day", "kind"],
        size=200,
    )
    return [h["_source"] | {"id": h["_id"]} for h in r["hits"]["hits"]]


def _slots(with_id: str, items: list[dict]) -> list[dict]:
    """Breaks free for both: the user's calendar and the other person's own agenda are both checked."""
    theirs = store.user_items(with_id)
    kinds = store.session_kinds([i.get("session_id") or "" for i in items + theirs])
    return store.free_slots(_food_sessions(), items, kinds, with_id, now(), other_items=theirs)


def _set_status(item: dict, status: str, extra: dict | None = None) -> dict:
    """Update this meeting and, when it came from a request, the other person's copy of it too."""
    change = {"status": status} | (extra or {})
    ids = {item["id"]} | {i["id"] for i in store.linked_items(item.get("request_id") or "")}
    for doc_id in ids:
        es.update(index=settings.idx_agenda, id=doc_id, doc=change)
    store.refresh()
    return item | change


def _own_item(item_id: str, user_id: str) -> dict:
    item = store.get_item(item_id)
    if item is None or item.get("user_id") != user_id or item.get("kind") != "meeting":
        raise HTTPException(status_code=404, detail=f"no meeting {item_id}")
    return item


def _answer(item_id: str, user_id: str, status: str, action: str) -> dict:
    """Accept or decline a request someone sent the user."""
    item = _own_item(item_id, user_id)
    span = trace.get_current_span()
    span.set_attribute("confox.connect.with_id", item.get("with_id") or "")
    if item.get("status") != "pending" or store.direction(item) != "incoming":
        raise HTTPException(status_code=409, detail=f"meeting {item_id} is not a pending request to you")
    extra: dict = {}
    if status == "confirmed" and not item.get("room") and item.get("session_id"):
        slot = store.get_session(item["session_id"])  # a request may name its break without the room
        if slot and slot.get("room"):
            extra["room"] = slot["room"]
    requests.add(1, {"action": action})
    updated = _set_status(item, status, extra)  # both copies share status and room; direction stays per side
    es.update(index=settings.idx_agenda, id=item_id, doc={"direction": "incoming"})
    store.refresh()
    return updated | {"direction": "incoming"}


@router.get("/slots")
def slots(user_id: str = Query(default_factory=lambda: settings.demo_user), with_id: str = Query(min_length=1)) -> dict:
    """Up to three breaks both people are free for: {"slots": [{session_id, title, starts_at, ends_at, room, day}]}."""
    found = _slots(with_id, store.user_items(user_id))
    trace.get_current_span().set_attribute("confox.connect.slots", len(found))
    return {"slots": found}


@router.get("")
def connections(user_id: str = Query(default_factory=lambda: settings.demo_user)) -> dict:
    """{"incoming": pending requests to the user, "outgoing": pending requests they sent, "meetings": confirmed}."""
    return store.split_connect(store.user_items(user_id))


@router.post("")
def send(body: SendRequest) -> dict:
    """Ask `with_id` to meet at the break `session_id`. 409 when a meeting with them already exists at that time."""
    span = trace.get_current_span()
    span.set_attribute("confox.connect.with_id", body.with_id)
    if body.with_id == body.user_id:
        raise HTTPException(status_code=422, detail="cannot meet yourself")
    person = _person(body.with_id)
    slot = store.get_session(body.session_id)
    if slot is None or not slot.get("is_food"):
        raise HTTPException(status_code=404, detail=f"no food or coffee break {body.session_id}")
    items = store.user_items(body.user_id)
    if store.clashing_meeting(items, body.with_id, slot["starts_at"], slot["ends_at"]):
        raise HTTPException(status_code=409, detail=f"already meeting {person['name']} at that time")
    doc_id = store.meeting_doc_id(body.user_id)
    request_id = doc_id.rsplit("-", 1)[-1]
    item = store.meeting_request(body.user_id, slot, person, body.message, request_id=request_id)
    es.create(index=settings.idx_agenda, id=doc_id, document=item)
    # The recipient gets the request as an incoming item they can accept or decline.
    sender = _person(body.user_id)
    es.create(
        index=settings.idx_agenda, id=store.meeting_doc_id(body.with_id), document=store.mirror_request(item, sender)
    )
    store.refresh()
    requests.add(1, {"action": "send"})
    return item | {"id": doc_id}


@router.post("/{item_id}/accept")
def accept(item_id: str, user_id: str = Query(default_factory=lambda: settings.demo_user)) -> dict:
    return _answer(item_id, user_id, "confirmed", "accept")


@router.post("/{item_id}/decline")
def decline(item_id: str, user_id: str = Query(default_factory=lambda: settings.demo_user)) -> dict:
    return _answer(item_id, user_id, "declined", "decline")


@router.post("/{item_id}/withdraw")
def withdraw(item_id: str, user_id: str = Query(default_factory=lambda: settings.demo_user)) -> dict:
    """Take back a request the user sent while it is still pending; the other person's copy goes too."""
    item = _own_item(item_id, user_id)
    if item.get("status") != "pending" or store.direction(item) != "outgoing":
        raise HTTPException(status_code=409, detail=f"meeting {item_id} is not a pending request you sent")
    requests.add(1, {"action": "withdraw"})
    return _set_status(item, "withdrawn")
