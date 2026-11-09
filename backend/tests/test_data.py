import json

import pytest

from app.config import RAW_SCHEDULE
from app.data.demo import emma_monday
from app.data.people import sample_attendees, speakers
from app.data.sessions import build_sessions, classify, strip_emoji


@pytest.fixture(scope="module")
def raw():
    return json.loads(RAW_SCHEDULE.read_text())


@pytest.fixture(scope="module")
def sessions(raw):
    return build_sessions(raw)


def test_strip_emoji():
    assert strip_emoji("☕ Coffee Break") == "Coffee Break"
    assert strip_emoji("⚡ Lightning Talks") == "Lightning Talks"
    assert strip_emoji("🍲 Lunch | On Own") == "Lunch | On Own"


@pytest.mark.parametrize(
    ("track", "title", "expected"),
    [
        ("Project Lightning Talks", "☕ Coffee Break", ("break", True)),
        ("Breaks", "🍲 Lunch", ("break", True)),
        ("Keynote Sessions", "Opening Keynote", ("keynote", False)),
        ("CNCF-hosted Co-located Events", "ArgoCon", ("colocated", False)),
        ("Lightning Talks", "Five minutes on eBPF", ("lightning", False)),
        ("Observability", "Anatomy of an Outage: When Bursty ML Workloads Break the Scheduler", ("talk", False)),
        (None, "Something new", ("talk", False)),
    ],
)
def test_classify(track, title, expected):
    assert classify(track, title) == expected


def test_every_session_with_a_time_is_loaded(raw, sessions):
    assert len(sessions) == sum(1 for s in raw["sessions"] if s.get("startsAt"))
    assert len({s["id"] for s in sessions}) == len(sessions)


def test_monday_food_is_found(sessions):
    monday_food = [s["title"] for s in sessions if s["day"] == "2026-11-09" and s["is_food"]]
    assert "Coffee Break" in monday_food
    assert any(t.startswith("Lunch") for t in monday_food)


def test_sample_attendees_are_stable_and_labelled():
    a, b = sample_attendees(), sample_attendees()
    assert a == b
    assert len(a) == 80 and len({p["id"] for p in a}) == 80
    assert all(p["sample"] for p in a)
    assert [p["id"] for p in a[:2]] == ["emma", "alice"]
    utah = [p["schools"][0] == "University of Utah" for p in a[2:]]
    assert utah == sorted(utah, reverse=True)  # University of Utah alumni first


def test_speakers_are_public_not_sample(raw):
    people = speakers(raw)
    assert len(people) == len(raw["speakers"])
    assert not any(p["sample"] for p in people)


def test_emma_monday(sessions):
    items = {i["id"]: i for i in emma_monday(sessions, sample_attendees())}
    assert items["emma-colocated"]["starts_at"] == "2026-11-09T09:00:00"
    assert items["emma-coffee-alice"]["starts_at"] == "2026-11-09T10:48:00"
    assert items["emma-coffee-alice"]["with_id"] == "alice"
    assert items["emma-lunch-request"]["status"] == "pending"
    assert all(i["sample"] for i in items.values())
