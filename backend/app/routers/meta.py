"""What the frontend needs to know about the demo: the current moment and who is signed in."""

from fastapi import APIRouter

from ..clock import now
from ..config import settings

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/meta")
def meta() -> dict[str, str]:
    return {"now": now().isoformat(), "user_id": settings.demo_user}
