"""What matters right now for the signed-in user: on now, starting soon, the next food break, and their next item.

The food logic is `next_food()` from app/now.py (docs/tasks/next-food.md).
"""

from datetime import timedelta

from fastapi import APIRouter

from ..clock import now as clock_now
from ..config import settings
from ..es import es
from ..now import next_food

router = APIRouter(prefix="/api/now", tags=["now"])

SOON_MINUTES = 90
FIELDS = [
    "title", "starts_at", "ends_at", "day", "minutes", "kind", "is_food", "track", "level",
    "projects", "room", "venue", "speaker_names", "companies",
]  # fmt: skip


def _sessions(day: str) -> list[dict]:
    r = es.search(
        index=settings.idx_sessions,
        size=300,
        source_includes=FIELDS,
        sort=[{"starts_at": "asc"}],
        query={"bool": {"filter": [{"term": {"day": day}}], "must_not": [{"term": {"kind": "registration"}}]}},
    )
    return [h["_source"] | {"id": h["_id"]} for h in r["hits"]["hits"]]


def split_now(sessions: list[dict], now_iso: str, soon_iso: str) -> tuple[list[dict], list[dict]]:
    """Sessions on now (short ones first, full-day co-located events last) and sessions starting before `soon_iso`."""
    on = [s for s in sessions if s["starts_at"] <= now_iso < s["ends_at"] and not s.get("is_food")]
    on.sort(key=lambda s: (s.get("kind") == "colocated", s["ends_at"]))
    soon = [s for s in sessions if now_iso < s["starts_at"] <= soon_iso]
    return on, soon


@router.get("")
def now_view(user_id: str | None = None) -> dict:
    current = clock_now()
    day = current.date().isoformat()
    now_iso = current.isoformat()
    soon_iso = (current + timedelta(minutes=SOON_MINUTES)).isoformat()
    sessions = _sessions(day)
    on, soon = split_now(sessions, now_iso, soon_iso)

    uid = user_id or settings.demo_user
    agenda = es.search(
        index=settings.idx_agenda,
        size=50,
        sort=[{"starts_at": "asc"}],
        query={"bool": {"filter": [{"term": {"user_id": uid}}, {"range": {"ends_at": {"gt": now_iso}}}]}},
    )["hits"]["hits"]
    upcoming = [h["_source"] for h in agenda if h["_source"].get("status") == "confirmed"]
    mine = next((a for a in upcoming if a.get("kind") == "meeting" or a["starts_at"] > now_iso), None)

    return {
        "now": now_iso,
        "on_now": on[:6],
        "on_now_total": len(on),
        "soon": soon[:8],
        "soon_total": len(soon),
        "food": next_food(sessions, current),
        "my_next": mine,
    }
