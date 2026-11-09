from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app, included
from app.routers import dashboard as dash

NOW = datetime(2026, 11, 9, 8, 40)


def test_router_is_discovered():
    assert "dashboard" in included


def test_sessions_body_scopes_the_day_and_next_90_minutes():
    body = dash.sessions_body("2026-11-09", NOW)
    assert body["size"] == 0
    day = body["aggs"]["day"]
    assert day["filter"] == {"term": {"day": "2026-11-09"}}

    hist = day["aggs"]["timeline"]["date_histogram"]
    assert hist["fixed_interval"] == "30m"
    assert hist["min_doc_count"] == 0
    assert hist["extended_bounds"] == {"min": "2026-11-09T07:00:00", "max": "2026-11-09T18:59:00"}
    assert hist["hard_bounds"] == {"min": "2026-11-09T07:00:00", "max": "2026-11-09T19:00:00"}

    soon = day["aggs"]["next_up"]["filter"]["bool"]
    assert soon["filter"] == [{"range": {"starts_at": {"gte": "2026-11-09T08:40:00", "lte": "2026-11-09T10:10:00"}}}]
    assert soon["must_not"] == [{"term": {"kind": "registration"}}]
    assert day["aggs"]["next_up"]["aggs"]["hits"]["top_hits"]["size"] == 6


def test_people_body_counts_sample_attendees_and_speaker_companies():
    aggs = dash.people_body()["aggs"]
    assert aggs["sample"]["filter"] == {"term": {"sample": True}}
    assert aggs["speakers"]["filter"] == {"term": {"kind": "speaker"}}
    assert aggs["speakers"]["aggs"]["companies"]["terms"]["exclude"] == [""]


def test_group_counts_folds_kinds_into_groups():
    buckets = [
        {"key": "lightning", "doc_count": 3},
        {"key": "talk", "doc_count": 1},
        {"key": "keynote", "doc_count": 2},
        {"key": "colocated", "doc_count": 4},
        {"key": "break", "doc_count": 1},
        {"key": "registration", "doc_count": 1},
        {"key": "poster", "doc_count": 2},
    ]
    assert dash.group_counts(buckets) == {"talks": 4, "keynotes": 2, "colocated": 4, "breaks": 1, "other": 3}


def _terms(*pairs):
    return {"buckets": [{"key": k, "doc_count": n} for k, n in pairs]}


def _bucket(start, *kinds):
    return {"key_as_string": start, "doc_count": sum(n for _, n in kinds), "kinds": _terms(*kinds)}


SESSIONS = {
    "hits": {"total": {"value": 600, "relation": "eq"}},
    "aggregations": {
        "speakers": {"value": 712},
        "tracks": {"value": 30},
        "days": _terms(("2026-11-09", 78), ("2026-11-10", 194)),
        "day": {
            "doc_count": 78,
            "speakers": {"value": 46},
            "tracks_count": {"value": 5},
            "tracks": _terms(("Project Lightning Talks", 51)),
            "kinds": _terms(("lightning", 48), ("registration", 2)),
            "timeline": {
                "buckets": [
                    _bucket("2026-11-09T07:00:00", ("registration", 2)),
                    _bucket("2026-11-09T07:30:00"),
                    _bucket("2026-11-09T09:00:00", ("colocated", 9)),
                ]
            },
            "next_up": {
                "doc_count": 9,
                "hits": {
                    "hits": {
                        "hits": [
                            {
                                "_id": "1289760",
                                "_source": {
                                    "title": "Cloud Native AI + Inference Day",
                                    "starts_at": "2026-11-09T09:00:00",
                                    "room": "Salt Palace | Level 2 | 254 ",
                                    "kind": "colocated",
                                },
                            }
                        ]
                    }
                },
            },
        },
    },
}

PEOPLE = {
    "aggregations": {
        "sample": {
            "doc_count": 80,
            "countries": _terms(("United States", 35), ("Brazil", 9)),
            "countries_count": {"value": 7},
        },
        "speakers": {"doc_count": 712, "companies": _terms(("Google", 51))},
    }
}


def test_shape_builds_the_payload():
    out = dash.shape("2026-11-09", NOW, SESSIONS, PEOPLE)
    assert out["now"] == "2026-11-09T08:40:00"
    assert out["is_today"] is True
    assert out["days"] == [{"day": "2026-11-09", "sessions": 78}, {"day": "2026-11-10", "sessions": 194}]
    assert out["stats"] == {
        "sessions_total": 600,
        "sessions_day": 78,
        "speakers_total": 712,
        "speakers_day": 46,
        "tracks_total": 30,
        "tracks_day": 5,
        "sample_attendees": 80,
        "countries": 7,
    }
    tl = out["timeline"]
    assert tl["interval_minutes"] == 30
    assert tl["groups"] == ["talks", "keynotes", "colocated", "breaks", "other"]
    assert [b["start"][11:16] for b in tl["buckets"]] == ["07:00", "07:30", "09:00"]
    assert tl["buckets"][0]["counts"]["other"] == 2
    assert tl["buckets"][1] == {"start": "2026-11-09T07:30:00", "total": 0, "counts": dict.fromkeys(dash.GROUPS, 0)}
    assert tl["buckets"][2]["counts"]["colocated"] == 9
    assert out["next_up"] == [
        {
            "id": "1289760",
            "title": "Cloud Native AI + Inference Day",
            "starts_at": "2026-11-09T09:00:00",
            "room": "Salt Palace | Level 2 | 254",
            "kind": "colocated",
        }
    ]
    assert out["next_up_total"] == 9
    assert out["tracks"] == [{"name": "Project Lightning Talks", "sessions": 51}]
    assert out["kinds"] == [{"kind": "lightning", "sessions": 48}, {"kind": "registration", "sessions": 2}]
    assert out["people"]["countries"][0] == {"name": "United States", "attendees": 35}
    assert out["people"]["companies"] == [{"name": "Google", "speakers": 51}]


def test_shape_marks_other_days_as_not_today():
    assert dash.shape("2026-11-10", NOW, SESSIONS, PEOPLE)["is_today"] is False


def test_endpoint_rejects_a_bad_day():
    assert TestClient(app).get("/api/dashboard", params={"day": "monday"}).status_code == 422
