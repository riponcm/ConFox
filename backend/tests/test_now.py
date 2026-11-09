from datetime import datetime

from app.now import next_food

MONDAY = "2026-11-09"


def session(
    session_id: str,
    title: str,
    starts_at: str | None,
    ends_at: str | None,
    *,
    day: str = MONDAY,
    is_food: bool = True,
) -> dict:
    return {
        "id": session_id,
        "title": title,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "day": day,
        "is_food": is_food,
    }


COFFEE = session("coffee", "Coffee Break", f"{MONDAY}T10:48:00", f"{MONDAY}T11:03:00")
LUNCH = session("lunch", "Lunch", f"{MONDAY}T12:46:00", f"{MONDAY}T13:30:00")


def test_returns_next_food_break_today():
    result = next_food([LUNCH, COFFEE], datetime(2026, 11, 9, 8, 40))

    assert result == {"session": COFFEE, "status": "next", "minutes": 128}


def test_returns_current_food_break_with_minutes_left():
    result = next_food([COFFEE, LUNCH], datetime(2026, 11, 9, 10, 55))

    assert result == {"session": COFFEE, "status": "now", "minutes": 8}


def test_returns_none_after_last_food_break():
    assert next_food([COFFEE, LUNCH], datetime(2026, 11, 9, 18, 0)) is None


def test_does_not_return_tomorrows_food_break():
    tomorrow = session("tomorrow", "Breakfast", "2026-11-10T08:00:00", "2026-11-10T09:00:00", day="2026-11-10")

    assert next_food([tomorrow], datetime(2026, 11, 9, 18, 0)) is None


def test_ignores_non_food_session_that_starts_sooner():
    talk = session("talk", "Opening Keynote", f"{MONDAY}T09:00:00", f"{MONDAY}T10:00:00", is_food=False)

    assert next_food([talk, COFFEE], datetime(2026, 11, 9, 8, 40))["session"] == COFFEE


def test_skips_session_with_missing_start_time():
    incomplete = session("incomplete", "Breakfast", None, f"{MONDAY}T09:00:00")

    assert next_food([incomplete], datetime(2026, 11, 9, 8, 40)) is None


def test_current_food_break_that_ends_last_wins():
    later = session("later", "Reception", f"{MONDAY}T10:50:00", f"{MONDAY}T11:30:00")

    assert next_food([COFFEE, later], datetime(2026, 11, 9, 10, 55))["session"] == later


def test_same_start_time_is_ordered_by_id():
    first = session("a", "Coffee A", f"{MONDAY}T10:48:00", f"{MONDAY}T11:03:00")
    second = session("b", "Coffee B", f"{MONDAY}T10:48:00", f"{MONDAY}T11:03:00")

    assert next_food([second, first], datetime(2026, 11, 9, 8, 40))["session"] == first
