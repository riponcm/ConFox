"""Session details: the pure shaping rules of GET /api/sessions/{id}; no Elasticsearch."""

import pytest

from app.data.people import speaker_links
from app.routers.sessions import (
    agenda_session_ids,
    cosine,
    detail,
    pick_similar,
    similar_body,
    similarity_bucket,
    speakers_out,
    title_has_words,
    track_later_body,
    why_matches,
)

DAY = "2026-11-09"
AI_DAY = {
    "id": "1289760",
    "title": "Cloud Native AI + Inference Day Hosted by CNCF - Full Day Event",
    "description": "A day on serving models.",
    "kind": "colocated",
    "track": "CNCF-hosted Co-located Events",
    "projects": [],
    "starts_at": f"{DAY}T09:00:00",
    "ends_at": f"{DAY}T17:30:00",
    "speaker_ids": [],
}
TALK = {
    "id": "t1",
    "title": "Who Ran Up the Inference Bill? AI Traffic Control with KServe",
    "description": "GPU scheduling for AI inference at scale.",
    "kind": "talk",
    "track": "AI + ML",
    "projects": ["KServe"],
    "starts_at": f"{DAY}T10:40:00",
    "ends_at": f"{DAY}T11:10:00",
    "speaker_ids": ["sp-1", "sp-2"],
    "speaker_names": ["Ada Lovelace", "Grace Hopper"],
}
EMMA = {"interests": ["AI inference", "GPU scheduling", "Platform engineering"], "projects": ["KServe"]}
AGENDA = [
    {
        "kind": "session",
        "status": "confirmed",
        "session_id": "1289760",
        **{k: AI_DAY[k] for k in ("starts_at", "ends_at")},
    },
    {
        "kind": "meeting",
        "status": "confirmed",
        "with_id": "alice",
        "with_name": "Alice Moreno",
        "title": "Coffee",
        "starts_at": f"{DAY}T10:48:00",
        "ends_at": f"{DAY}T11:03:00",
    },
    {"kind": "meeting", "status": "pending", "with_id": "liam", "starts_at": f"{DAY}T12:46:00", "ends_at": "x"},
]


def hit(_id: str, score: float | None = None, **source) -> dict:
    return {"_id": _id, "_score": score, "_source": source}


def test_cosine_handles_missing_and_mismatched_vectors():
    assert cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine(None, [1.0]) is None
    assert cosine([1.0, 2.0], [1.0]) is None
    assert cosine([0.0, 0.0], [0.0, 0.0]) is None


@pytest.mark.parametrize(
    ("score", "bucket"),
    [(0.55, "very_close"), (0.48, "very_close"), (0.446, "close"), (0.40, "related"), (0.2, "distant")],
)
def test_similarity_buckets(score, bucket):
    assert similarity_bucket(score)["bucket"] == bucket


def test_no_vectors_no_bucket():
    assert similarity_bucket(None) is None


def test_title_has_words_in_any_order():
    assert title_has_words(AI_DAY["title"], "AI inference")
    assert not title_has_words(AI_DAY["title"], "GPU scheduling")
    assert not title_has_words("Detailed talk", "AI")  # whole words only


def test_why_lists_interests_projects_and_closeness():
    why = why_matches(TALK, EMMA, similarity_bucket(0.5))
    kinds = [w["kind"] for w in why]
    labels = [w["label"] for w in why]
    assert "Matches AI inference" in labels and "Matches GPU scheduling" in labels
    assert "Uses KServe" in labels
    assert kinds[-1] == "similar"
    assert len(labels) == len(set(labels))


def test_why_for_the_ai_day_uses_title_words_and_skips_distant_vectors():
    why = why_matches(AI_DAY, EMMA, similarity_bucket(0.3))
    assert [w["label"] for w in why] == ["Related to AI inference"]


def test_why_track_match_reads_as_track():
    session = TALK | {"title": "Untitled", "description": "", "projects": [], "track": "Platform Engineering"}
    why = why_matches(session, {"interests": ["Platform engineering"]}, None)
    assert why == [
        {"kind": "track", "label": "Track: Platform Engineering", "value": "Platform engineering", "where": "track"}
    ]


def test_agenda_session_ids_are_confirmed_sessions_only():
    items = AGENDA + [{"kind": "session", "status": "declined", "session_id": "gone"}]
    assert agenda_session_ids(items) == {"1289760"}


def test_similar_prefers_knn_then_track_then_nothing():
    knn = [hit("a", 0.91234, title="A", starts_at="x"), hit("b", 0.8, title="B")]
    track = [hit("c", None, title="C")]
    got = pick_similar(knn, track, {"b"})
    assert got["basis"] == "semantic"
    assert [(i["id"], i.get("score"), i["on_agenda"]) for i in got["items"]] == [("a", 0.912, False), ("b", 0.8, True)]
    fallback = pick_similar([], track, set())
    assert fallback["basis"] == "track" and [i["id"] for i in fallback["items"]] == ["c"]
    assert pick_similar([], [], set()) == {"basis": "none", "items": []}


def test_similar_body_excludes_itself_and_breaks():
    body = similar_body("t1", [0.1, 0.2])
    flt = body["knn"]["filter"]["bool"]["must_not"]
    assert {"ids": {"values": ["t1"]}} in flt
    assert {"term": {"is_food": True}} in flt
    assert body["knn"]["k"] == 5 and body["size"] == 5


def test_track_later_needs_a_track_and_starts_here():
    assert track_later_body(TALK | {"track": None}) is None
    body = track_later_body(TALK)
    assert {"range": {"starts_at": {"gte": TALK["starts_at"]}}} in body["query"]["bool"]["filter"]
    assert body["sort"] == [{"starts_at": "asc"}]


def test_speakers_keep_session_order_and_fall_back_to_published_names():
    people = [
        hit(
            "sp-1",
            bio="x" * 900,
            name="Ada Lovelace",
            title="Engineer",
            company="Analytical",
            links=[{"title": "Blog", "url": "https://ada.dev"}, {"title": "Bad", "url": "javascript:alert(1)"}],
        )
    ]
    others = [
        hit("o1", title="Other one", starts_at="a", speaker_ids=["sp-1"]),
        hit("o2", title="Grace solo", starts_at="b", speaker_ids=["sp-2"]),
    ]
    out = speakers_out(TALK, people, others, {"o1"})
    assert [s["name"] for s in out] == ["Ada Lovelace", "Grace Hopper"]
    assert len(out[0]["bio"]) == 600 and out[0]["bio"].endswith("…")
    assert out[0]["links"] == [{"title": "Blog", "url": "https://ada.dev"}]
    assert [(o["id"], o["on_agenda"]) for o in out[0]["other_sessions"]] == [("o1", True)]
    assert out[1]["title"] == "" and [o["id"] for o in out[1]["other_sessions"]] == ["o2"]


def test_detail_puts_it_together():
    going = {
        "aggregations": {
            "sessions": {
                "buckets": [
                    {
                        "key": "t1",
                        "doc_count": 4,
                        "people": {"value": 4},
                        "friends": {"who": {"buckets": [{"key": "alice"}]}},
                    }
                ]
            }
        }
    }
    parts = {
        "going": going,
        "transcript": {"hits": {"total": {"value": 8}, "hits": []}},
        "speakers": None,  # a failed part leaves its list empty
        "similar": {"hits": {"hits": [hit("s1", 0.9, title="Close one")]}},
        "track_later": {"hits": {"hits": [hit("l1", None, title="Later")]}},
    }
    out = detail(TALK, EMMA, [1.0, 0.0], [1.0, 0.0], AGENDA, {"1289760": "colocated"}, parts, {"alice": "Alice Moreno"})
    assert out["on_agenda"] is False and out["can_add"] is True
    assert out["clashes"] == ["Coffee with Alice Moreno"]  # the co-located day on the agenda does not clash
    assert (out["going"], out["going_names"]) == (4, ["Alice Moreno"])
    assert out["catch_up"] == {"available": True, "chunks": 8}
    assert out["similar"]["basis"] == "semantic" and out["same_track_later"][0]["id"] == "l1"
    assert [s["name"] for s in out["speakers"]] == ["Ada Lovelace", "Grace Hopper"]
    assert out["similarity"]["bucket"] == "very_close"
    assert out["slides_url"] is None


def test_detail_of_the_agenda_day_itself():
    parts = {"going": None, "transcript": None}
    out = detail(AI_DAY, EMMA, None, None, AGENDA, {"1289760": "colocated"}, parts, {})
    assert out["on_agenda"] is True
    assert out["clashes"] == ["Coffee with Alice Moreno"]  # a co-located day shows what it overlaps
    assert out["going"] == 0 and out["catch_up"]["available"] is False
    assert out["similar"] == {"basis": "none", "items": []}
    assert out["similarity"] is None


def test_breaks_cannot_be_added():
    out = detail(TALK | {"kind": "break", "is_food": True}, {}, None, None, [], {}, {}, {})
    assert out["can_add"] is False


def test_speaker_links_keep_web_urls():
    raw = {"links": [{"title": "LinkedIn", "url": "https://linkedin.com/in/x"}, {"linkType": "Blog", "url": "ftp://x"}]}
    assert speaker_links(raw) == [{"title": "LinkedIn", "url": "https://linkedin.com/in/x"}]
    assert speaker_links({}) == []
