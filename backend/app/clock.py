"""One clock for the whole app: the demo moment when DEMO_NOW is set, otherwise local time in Salt Lake City.

Schedule times are local conference time without an offset, so "now" is a naive datetime in the same local time.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from .config import settings

CONFERENCE_TZ = ZoneInfo("America/Denver")


def now() -> datetime:
    if settings.demo_now:
        return datetime.fromisoformat(settings.demo_now)
    return datetime.now(CONFERENCE_TZ).replace(tzinfo=None, microsecond=0)
