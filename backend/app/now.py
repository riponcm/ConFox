"""Helpers for the Now page."""

from datetime import datetime


def next_food(sessions: list[dict], now: datetime) -> dict | None:
    """Return the current food break, or the next food break today."""
    food = []
    for session in sessions:
        if not session.get("is_food") or not session.get("starts_at") or not session.get("ends_at"):
            continue
        food.append(
            (
                session,
                datetime.fromisoformat(session["starts_at"]),
                datetime.fromisoformat(session["ends_at"]),
            )
        )

    current = [item for item in food if item[1] <= now < item[2]]
    if current:
        session, _, ends_at = max(current, key=lambda item: item[2])
        return {
            "session": session,
            "status": "now",
            "minutes": int((ends_at - now).total_seconds() // 60),
        }

    today = now.date().isoformat()
    upcoming = [item for item in food if item[0].get("day") == today and item[1] > now]
    if not upcoming:
        return None

    session, starts_at, _ = min(upcoming, key=lambda item: (item[1], str(item[0].get("id", ""))))
    return {
        "session": session,
        "status": "next",
        "minutes": int((starts_at - now).total_seconds() // 60),
    }
