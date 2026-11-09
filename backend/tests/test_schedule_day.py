"""Day view extras (going, overlaps of co-located events, summary, facets, profile chips); no Elasticsearch."""

from app.routers.schedule import (
    annotate,
    day_extras,
    day_facets,
    friends,
    going_body,
    on_day,
    parse_going,
    profile_chips,
    summary,
)
from tests.test_schedule import AGENDA, COFFEE, COLOCATED, DAY, EMMA, by_id, session

ALICE_COFFEE = {
    "kind": "meeting",
    "status": "confirmed",
    "with_id": "alice",
    "with_name": "Alice Moreno",
    "title": "Coffee",
    "starts_at": f"{DAY}T10:48:00",
    "ends_at": f"{DAY}T11:03:00",
}
LIAM_LUNCH = {
    "kind": "meeting",
    "status": "pending",
    "with_id": "att-001",
    "with_name": "Liam Haddad",
    "starts_at": f"{DAY}T12:46:00",
    "ends_at": f"{DAY}T13:30:00",
}
MATCHES = [
    {"id": "alice", "name": "Alice Moreno"},
    {"id": "quinn", "name": "Quinn Park"},
    {"id": "maya", "name": "Maya"},
]


def test_profile_chips_are_interests_then_projects_without_repeats():
    profile = {"interests": ["AI inference", " KServe ", ""], "projects": ["KServe", "Kubeflow"]}
    assert profile_chips(profile) == ["AI inference", "KServe", "Kubeflow"]
    assert profile_chips({}) == []


def test_on_day_keeps_items_starting_that_day():
    other = {"starts_at": "2026-11-10T09:00:00"}
    assert on_day([ALICE_COFFEE, other, {}], DAY) == [ALICE_COFFEE]


def test_friends_are_meeting_partners_then_top_matches():
    people = friends([LIAM_LUNCH, ALICE_COFFEE], MATCHES, limit=2)
    # Alice comes from the confirmed meeting; the pending request does not make Liam one of the user's people.
    assert people == {"alice": "Alice Moreno", "quinn": "Quinn Park"}


def test_going_body_counts_everyone_but_the_user_and_names_only_friends():
    body = going_body(["s1", "s2"], "emma", ["alice"])
    q = body["query"]["bool"]
    assert {"terms": {"session_id": ["s1", "s2"]}} in q["filter"]
    assert {"term": {"status": "confirmed"}} in q["filter"]
    assert q["must_not"] == [{"term": {"user_id": "emma"}}]
    sessions = body["aggs"]["sessions"]
    assert sessions["terms"] == {"field": "session_id", "size": 2}
    assert sessions["aggs"]["friends"]["filter"] == {"terms": {"user_id": ["alice"]}}
    assert "friends" not in going_body(["s1"], "emma", [])["aggs"]["sessions"]["aggs"]


def test_parse_going_orders_names_like_friends_and_caps_them():
    people = {"alice": "Alice Moreno", "quinn": "Quinn Park", "maya": "Maya", "noah": "Noah"}
    who = [{"key": k} for k in ("noah", "maya", "quinn", "alice")]
    aggs = {
        "sessions": {
            "buckets": [
                {"key": "s1", "doc_count": 6, "people": {"value": 5}, "friends": {"who": {"buckets": who}}},
                {"key": "s2", "doc_count": 2, "people": {"value": 2}},
            ]
        }
    }
    out = parse_going(aggs, people, limit=3)
    assert out["s1"] == {"going": 5, "going_names": ["Alice Moreno", "Quinn Park", "Maya"]}
    assert out["s2"] == {"going": 2, "going_names": []}
    assert parse_going({}, people) == {}


def test_day_extras_adds_going_and_shows_what_a_colocated_event_overlaps():
    talk = session("t", "14:00", "14:30", "Something else")
    other_day = session("argo", "09:00", "17:30", "ArgoCon", kind="colocated")
    sessions = [COLOCATED, other_day, COFFEE, talk]
    agenda = AGENDA[:1] + [ALICE_COFFEE, LIAM_LUNCH]
    going = {"argo": {"going": 3, "going_names": ["Alice Moreno"]}}
    out = by_id(day_extras(annotate(sessions, EMMA, agenda), agenda, going))
    assert out["argo"]["going"] == 3 and out["argo"]["going_names"] == ["Alice Moreno"]
    assert out["t"]["going"] == 0 and out["t"]["going_names"] == []
    # Co-located events show the coffee they overlap; the co-located day on the agenda is still not a blocker,
    # breaks never show one, and the pending lunch does not count.
    assert out["argo"]["clashes"] == ["Coffee with Alice Moreno"]
    assert out["day"]["clashes"] == ["Coffee with Alice Moreno"]
    assert out["coffee"]["clashes"] == [] and out["t"]["clashes"] == []


def test_summary_and_facets():
    sessions = [
        {"for_you": True, "on_agenda": True, "kind": "colocated", "track": "CNCF", "venue": "Salt Palace"},
        {"for_you": True, "kind": "lightning", "track": "Lightning", "venue": "Hyatt", "level": None},
        {"for_you": False, "kind": "lightning", "track": "Lightning", "venue": "Hyatt", "level": "Beginner"},
    ]
    assert summary(sessions) == {"for_you": 2, "total": 3, "on_agenda": 1}
    facets = day_facets(sessions)
    assert facets["kind"] == [{"key": "lightning", "count": 2}, {"key": "colocated", "count": 1}]
    assert facets["level"] == [{"key": "Beginner", "count": 1}]
    assert facets["venue"][0] == {"key": "Hyatt", "count": 2}
    assert day_facets([])["track"] == []


def test_top_matches_uses_the_people_ranking(monkeypatch):
    """Going names come from the same ranking as People; a signature change there must not break the day view."""
    from app.routers import schedule

    calls = []

    def fake_rank(user_id, user, vector, q="", kind=None, post=None, aggs=None, size=20):
        calls.append((user_id, size))
        return [{"id": "alice", "name": "Alice Moreno"}], {}, "bm25"

    monkeypatch.setattr(schedule, "rank_people", fake_rank)
    assert schedule._top_matches("emma", {"interests": ["AI inference"]}, None) == [
        {"id": "alice", "name": "Alice Moreno"}
    ]
    assert calls == [("emma", schedule.FRIENDS)]


def test_top_matches_is_empty_when_ranking_fails(monkeypatch):
    from app.routers import people, schedule

    def failing(*_args, **_kwargs):
        raise people.SearchFailed("people index is rebuilding")

    monkeypatch.setattr(schedule, "rank_people", failing)
    assert schedule._top_matches("emma", {"interests": ["AI inference"]}, None) == []
