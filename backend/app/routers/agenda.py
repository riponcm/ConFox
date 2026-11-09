"""Add to agenda: the user's confirmed sessions and meetings, and adding or removing a session.

The document shape and the pure rules live in app/agenda_store.py, shared with Meet (routers/connect.py).
"""

import logging

from elasticsearch import ConflictError
from fastapi import APIRouter, HTTPException, Query
from opentelemetry import metrics, trace
from pydantic import BaseModel, Field

from .. import agenda_store as store
from ..config import settings
from ..es import es

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agenda", tags=["agenda"])
changes = metrics.get_meter("confox.agenda").create_counter(
    "confox.agenda.changes", unit="{change}", description="Sessions added to or removed from an agenda"
)

DAY_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
NOT_ADDABLE = {"break", "registration"}


class AddSession(BaseModel):
    user_id: str = Field(default_factory=lambda: settings.demo_user, min_length=1)
    session_id: str = Field(min_length=1)


def _session_items(user_id: str, session_id: str) -> list[dict]:
    r = es.search(
        index=settings.idx_agenda,
        query={
            "bool": {
                "filter": [
                    {"term": {"user_id": user_id}},
                    {"term": {"kind": "session"}},
                    {"term": {"session_id": session_id}},
                ]
            }
        },
        size=10,
    )
    return [h["_source"] | {"id": h["_id"]} for h in r["hits"]["hits"]]


@router.get("")
def agenda(
    user_id: str = Query(default_factory=lambda: settings.demo_user),
    day: str | None = Query(default=None, pattern=DAY_PATTERN),
) -> dict:
    """{"items": confirmed sessions and meetings by start time, "pending": pending meetings}, each with `id`."""
    return store.split_agenda(store.user_items(user_id, day))


@router.post("")
def add(body: AddSession) -> dict:
    """Put a session on the user's agenda. Idempotent: an existing entry (seeded ones included) is returned."""
    span = trace.get_current_span()
    span.set_attribute("confox.agenda.session_id", body.session_id)
    existing = _session_items(body.user_id, body.session_id)
    if existing:
        span.set_attribute("confox.agenda.existing", True)
        return existing[0]
    session = store.get_session(body.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"unknown session {body.session_id}")
    if session.get("kind") in NOT_ADDABLE or session.get("is_food"):
        raise HTTPException(status_code=422, detail="breaks and registration are not agenda items")
    doc_id = store.session_doc_id(body.user_id, body.session_id)
    item = store.session_item(body.user_id, session)
    try:
        es.create(index=settings.idx_agenda, id=doc_id, document=item)
    except ConflictError:
        # A double click raced us; the document is there, which is all the caller wanted.
        log.info("agenda: %s already exists", doc_id)
    else:
        changes.add(1, {"action": "add"})
    store.refresh()
    return item | {"id": doc_id}


@router.delete("/{session_id}")
def remove(session_id: str, user_id: str = Query(default_factory=lambda: settings.demo_user)) -> dict:
    """Take a session off the agenda: every session entry of this user for it (seeded ids differ, so by query)."""
    r = es.delete_by_query(
        index=settings.idx_agenda,
        query={
            "bool": {
                "filter": [
                    {"term": {"user_id": user_id}},
                    {"term": {"kind": "session"}},
                    {"term": {"session_id": session_id}},
                ]
            }
        },
        refresh=True,
    )
    deleted = int(r["deleted"])
    trace.get_current_span().set_attribute("confox.agenda.deleted", deleted)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"session {session_id} is not on the agenda")
    changes.add(1, {"action": "remove"})
    return {"session_id": session_id, "deleted": deleted}
