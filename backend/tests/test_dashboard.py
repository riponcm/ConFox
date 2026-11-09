from datetime import datetime

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app, included
from app.routers import dashboard as dash

NOW = datetime(2026, 11, 9, 8, 40)


def test_router_is_discovered():
    assert "dashboard" in included


def test_bodies_run_one_search_per_index_with_no_documents():
    reqs = dash.bodies("2026-11-09", NOW, "emma")
    assert [index for index, _ in reqs] == [
        settings.idx_sessions,
        settings.idx_people,
        settings.idx_agenda,
        settings.idx_activity,
    ]
    assert all(body["size"] == 0 for _, body in reqs)


def test_sessions_body_scopes_the_day():
    day = dash.sessions_body("2026-11-09")["aggs"]["day"]
    assert day["filter"] == {"term": {"day": "2026-11-09"}}
    hist = day["aggs"]["timeline"]["date_histogram"]
    assert hist["fixed_interval"] == "30m"
    assert hist["min_doc_count"] == 0
    assert hist["extended_bounds"] == {"min": "2026-11-09T07:00:00", "max": "2026-11-09T18:59:00"}
    assert hist["hard_bounds"] == {"min": "2026-11-09T07:00:00", "max": "2026-11-09T19:00:00"}


def test_people_body_looks_at_attendees_and_counts_the_host_school():
    aggs = dash.people_body()["aggs"]
    att = aggs["attendees"]
    assert att["filter"] == {"term": {"kind": "attendee"}}
    assert att["aggs"]["host_school"]["filter"] == {"term": {"schools": "University of Utah"}}
    assert {k for k in att["aggs"]} == {"countries", "schools", "host_school", "companies", "interests"}
    assert aggs["sample"]["filter"] == {"term": {"sample": True}}


def test_agenda_body_fills_from_now_on_today_and_the_whole_day_later():
    f = dash.agenda_body("2026-11-09", NOW, "emma")["aggs"]["filling"]["filter"]["bool"]["filter"]
    assert {"range": {"starts_at": {"gt": "2026-11-09T08:40:00", "lt": "2026-11-10T00:00:00"}}} in f
    assert {"term": {"status": "confirmed"}} in f

    later = dash.agenda_body("2026-11-11", NOW, "emma")["aggs"]
    assert {"range": {"starts_at": {"gt": "2026-11-10T23:59:59", "lt": "2026-11-12T00:00:00"}}} in later["filling"][
        "filter"
    ]["bool"]["filter"]
    assert later["filling"]["aggs"]["sessions"]["terms"]["order"] == [{"_count": "desc"}, {"start": "asc"}]
    assert {"term": {"user_id": "emma"}} in later["mine"]["filter"]["bool"]["filter"]


def test_activity_body_scopes_the_day_and_searches_all_week():
    aggs = dash.activity_body("2026-11-09")["aggs"]
    assert aggs["day"]["filter"] == {"range": {"at": {"gte": "2026-11-09T00:00:00", "lt": "2026-11-10T00:00:00"}}}
    assert aggs["day"]["aggs"]["timeline"]["date_histogram"]["field"] == "at"
    assert aggs["searches"]["filter"] == {"term": {"kind": "search"}}
    assert aggs["searches"]["aggs"]["terms"]["terms"]["field"] == "detail"


def test_covered_hours_counts_overlaps_once():
    items = [
        {"starts_at": "2026-11-09T09:00:00", "ends_at": "2026-11-09T17:30:00"},
        {"starts_at": "2026-11-09T10:48:00", "ends_at": "2026-11-09T11:03:00"},
        {"starts_at": "2026-11-09T18:00:00", "ends_at": "2026-11-09T18:30:00"},
        {"starts_at": "2026-11-09T18:00:00", "ends_at": "2026-11-09T18:00:00"},  # empty: ignored
    ]
    assert dash.covered_hours(items) == 9.0
    assert dash.covered_hours([]) == 0


def _item(kind, status, start, end, direction=None):
    item = {"kind": kind, "status": status, "starts_at": start, "ends_at": end}
    return item | ({"direction": direction} if direction else {})


MINE = [
    _item("session", "confirmed", "2026-11-09T09:00:00", "2026-11-09T17:30:00"),
    _item("meeting", "confirmed", "2026-11-09T10:48:00", "2026-11-09T11:03:00"),
    _item("meeting", "pending", "2026-11-09T12:46:00", "2026-11-09T13:30:00"),  # no direction: incoming
    _item("meeting", "pending", "2026-11-09T15:00:00", "2026-11-09T15:30:00", "outgoing"),
    _item("session", "declined", "2026-11-09T07:00:00", "2026-11-09T08:00:00"),
]


def test_my_day_counts_confirmed_hours_and_incoming_requests():
    assert dash.my_day(MINE) == {"hours": 8.5, "goal_hours": 8, "sessions": 1, "meetings": 1, "requests": 1}


def test_mine_per_bucket_marks_the_half_hour_an_item_starts_in():
    starts = ["2026-11-09T09:00:00", "2026-11-09T09:30:00", "2026-11-09T10:00:00", "2026-11-09T10:30:00"]
    assert dash.mine_per_bucket(starts, MINE) == [1, 0, 0, 1]


def test_pin_school_puts_the_host_first():
    buckets = [
        {"key": "TU Munich", "doc_count": 12},
        {"key": "Brigham Young University", "doc_count": 8},
        {"key": "University of Utah", "doc_count": 8},
        {"key": "UC Berkeley", "doc_count": 7},
    ]
    assert dash.pin_school(buckets, 8, size=3) == [
        {"name": "University of Utah", "count": 8, "pinned": True},
        {"name": "TU Munich", "count": 12},
        {"name": "Brigham Young University", "count": 8},
    ]
    assert dash.pin_school(buckets[:2], 0, size=3)[0] == {"name": "TU Munich", "count": 12}


def _terms(*pairs):
    return {"buckets": [{"key": k, "doc_count": n} for k, n in pairs]}


def _hist(*pairs):
    return {"buckets": [{"key_as_string": k, "doc_count": n} for k, n in pairs]}


SESSIONS = {
    "hits": {"total": {"value": 600, "relation": "eq"}},
    "aggregations": {
        "days": _terms(("2026-11-09", 78), ("2026-11-10", 194)),
        "day": {
            "doc_count": 78,
            "tracks": _terms(("Project Lightning Talks", 51)),
            "timeline": _hist(("2026-11-09T07:00:00", 2), ("2026-11-09T08:30:00", 0), ("2026-11-09T09:00:00", 9)),
        },
    },
}

PEOPLE = {
    "hits": {"total": {"value": 792, "relation": "eq"}},
    "aggregations": {
        "kinds": _terms(("speaker", 712), ("attendee", 80)),
        "sample": {"doc_count": 80},
        "attendees": {
            "doc_count": 80,
            "countries": _terms(("United States", 35)),
            "schools": _terms(("TU Munich", 12), ("University of Utah", 8)),
            "host_school": {"doc_count": 8},
            "companies": _terms(("Redwood Labs", 15)),
            "interests": _terms(("Multi-cluster", 33)),
        },
    },
}

AGENDA = {
    "aggregations": {
        "filling": {
            "doc_count": 12,
            "sessions": {
                "buckets": [
                    {
                        "key": "1289760",
                        "doc_count": 5,
                        "start": {"value_as_string": "2026-11-09T09:00:00"},
                        "doc": {
                            "hits": {
                                "hits": [
                                    {
                                        "_source": {
                                            "title": "Cloud Native AI + Inference Day",
                                            "starts_at": "2026-11-09T09:00:00",
                                            "room": "Salt Palace | Level 2 | 254 ",
                                        }
                                    }
                                ]
                            }
                        },
                    }
                ]
            },
        },
        "mine": {"doc_count": len(MINE), "items": {"hits": {"hits": [{"_source": i} for i in MINE]}}},
    }
}

ACTIVITY = {
    "aggregations": {
        "day": {
            "doc_count": 160,
            "sample": {"doc_count": 158},
            "kinds": _terms(("search", 62), ("match", 47)),
            "timeline": _hist(("2026-11-09T07:00:00", 0), ("2026-11-09T08:30:00", 40), ("2026-11-09T09:00:00", 0)),
        },
        "searches": {"doc_count": 62, "terms": _terms(("platform engineering", 10))},
    }
}


def test_shape_builds_the_payload():
    out = dash.shape("2026-11-09", NOW, SESSIONS, PEOPLE, AGENDA, ACTIVITY)
    assert out["now"] == "2026-11-09T08:40:00"
    assert out["is_today"] is True
    assert out["days"] == [{"day": "2026-11-09", "sessions": 78}, {"day": "2026-11-10", "sessions": 194}]
    assert out["sessions"] == {"total": 600, "day": 78}
    assert out["timeline"] == {
        "interval_minutes": 30,
        "buckets": [
            {"start": "2026-11-09T07:00:00", "total": 2, "mine": 0},
            {"start": "2026-11-09T08:30:00", "total": 0, "mine": 0},
            {"start": "2026-11-09T09:00:00", "total": 9, "mine": 1},
        ],
    }
    assert out["tracks"] == [{"name": "Project Lightning Talks", "sessions": 51}]
    assert out["filling"] == [
        {
            "id": "1289760",
            "title": "Cloud Native AI + Inference Day",
            "starts_at": "2026-11-09T09:00:00",
            "room": "Salt Palace | Level 2 | 254",
            "going": 5,
        }
    ]
    assert out["my_day"]["hours"] == 8.5
    people = out["people"]
    assert (people["total"], people["speakers"], people["attendees"], people["sample"]) == (792, 712, 80, 80)
    assert people["schools"][0] == {"name": "University of Utah", "count": 8, "pinned": True}
    assert people["countries"] == [{"name": "United States", "count": 35}]
    act = out["activity"]
    assert (act["total"], act["sample"]) == (160, 158)
    assert act["kinds"][0] == {"kind": "search", "count": 62}
    # Today stops at the half hour holding now: 09:00 is still to come.
    assert [b["start"][11:16] for b in act["buckets"]] == ["07:00", "08:30"]
    assert act["searches"] == [{"name": "platform engineering", "count": 10}]


def test_shape_keeps_every_activity_bucket_on_other_days():
    out = dash.shape("2026-11-10", NOW, SESSIONS, PEOPLE, AGENDA, ACTIVITY)
    assert out["is_today"] is False
    assert len(out["activity"]["buckets"]) == 3


def test_msearch_raises_when_one_body_fails(monkeypatch):
    class FakeES:
        def msearch(self, searches):
            assert searches[0] == {"index": settings.idx_sessions}
            return {"responses": [{"aggregations": {}}, {"error": {"type": "index_not_found_exception"}}]}

    monkeypatch.setattr(dash, "es", FakeES())
    r = TestClient(app).get("/api/dashboard")
    assert r.status_code == 503


def test_endpoint_rejects_a_bad_day():
    assert TestClient(app).get("/api/dashboard", params={"day": "monday"}).status_code == 422
