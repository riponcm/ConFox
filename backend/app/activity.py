"""What people do in Confox, kept in Elasticsearch so the Dashboard can aggregate it.

Each event is one small document: when, who, what kind, and a short detail (a search phrase, a session id).
Recording is best effort: a failure is logged and never breaks the request that triggered it.
"""

import logging

from .clock import now
from .config import settings
from .es import es

log = logging.getLogger(__name__)

KINDS = (
    "search",
    "match",
    "agenda_add",
    "agenda_remove",
    "connect_request",
    "connect_accept",
    "connect_decline",
    "connect_withdraw",
    "question",
)
DETAIL_CHARS = 60


def event(kind: str, user_id: str = "", detail: str = "", at: str | None = None, sample: bool = False) -> dict:
    return {
        "at": at or now().isoformat(timespec="seconds"),
        "user_id": user_id,
        "kind": kind,
        "detail": " ".join(detail.lower().split())[:DETAIL_CHARS],
        "sample": sample,
    }


def record(kind: str, user_id: str = "", detail: str = "") -> None:
    try:
        es.index(index=settings.idx_activity, document=event(kind, user_id, detail))
    except Exception as exc:  # the user's action already succeeded; losing one analytics event is acceptable
        log.warning("activity %s not recorded: %s", kind, exc)
