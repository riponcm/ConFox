"""Pure parts of People Match: reasons, query building and group parsing. No Elasticsearch needed."""

from app.routers.people import (
    BOOST,
    build_filters,
    build_group_aggs,
    build_match_query,
    parse_groups,
    related_topics,
    why,
)

EMMA = {
    "name": "Emma Carter",
    "company": "Wasatch Cloud",
    "interests": ["AI inference", "GPU scheduling", "Platform engineering", "Kubeflow", "KServe"],
    "schools": ["University of Utah"],
    "past_companies": ["Copperleaf"],
    "communities": ["Women in Cloud Native"],
    "city": "Salt Lake City",
    "country": "United States",
}
ALICE = {
    "kind": "attendee",
    "company": "Redwood Labs",
    "interests": ["AI inference", "GPU scheduling", "KServe", "vLLM"],
    "schools": ["University of Utah"],
    "past_companies": ["Wasatch Cloud"],
    "communities": ["Kubernetes contributors"],
    "city": "Salt Lake City",
}


def test_why_puts_schools_first_then_an_interest():
    assert why(EMMA, ALICE) == [
        {"label": "University of Utah alumni", "field": "schools", "value": "University of Utah"},
        {"label": "Both into AI inference", "field": "interests", "value": "AI inference"},
        {"label": "Worked at Wasatch Cloud", "field": "company", "value": "Wasatch Cloud"},
    ]


def test_why_is_capped_at_three_and_handles_missing_fields():
    assert len(why(EMMA, ALICE | {"communities": ["Women in Cloud Native"]})) == 3
    assert why(EMMA, {"name": "Nobody"}) == []
    assert why({}, ALICE) == []


def test_why_current_company_and_city():
    person = {"company": "Copperleaf", "city": "Salt Lake City"}
    assert why(EMMA, person) == [
        {"label": "Works at Copperleaf", "field": "company", "value": "Copperleaf"},
        {"label": "Also in Salt Lake City", "field": "city", "value": "Salt Lake City"},
    ]


def test_speaker_tracks_relate_to_interests():
    speaker = {"kind": "speaker", "interests": ["AI Inference + Agentic", "Security"], "bio": "Kubeflow maintainer."}
    assert related_topics(EMMA, speaker) == ["AI Inference + Agentic"]
    assert why(EMMA, speaker) == [
        {"label": "Speaks on AI Inference + Agentic", "field": "interests", "value": "AI Inference + Agentic"},
        {"label": "Mentions Kubeflow", "field": "q", "value": "Kubeflow"},
    ]


def _constant_scores(query: dict) -> list[tuple[dict, float]]:
    return [
        (c["constant_score"]["filter"], c["constant_score"]["boost"])
        for c in query["bool"]["should"]
        if "constant_score" in c
    ]


def test_query_boosts_shared_values_with_schools_highest():
    query = build_match_query("emma", EMMA)
    boosts = _constant_scores(query)
    assert ({"terms": {"schools": ["University of Utah"]}}, BOOST["schools"]) in boosts
    assert max(b for _, b in boosts) == BOOST["schools"]
    assert len([f for f, _ in boosts if "terms" in f and "interests" in f["terms"]]) == 5  # one per interest
    company = [f for f, b in boosts if b == BOOST["company"]]
    assert company[0]["bool"]["should"][1] == {"terms": {"past_companies": ["Wasatch Cloud", "Copperleaf"]}}
    assert query["bool"]["must_not"] == [{"ids": {"values": ["emma"]}}]
    assert query["bool"]["minimum_should_match"] == 0
    assert "must" not in query["bool"] and "filter" not in query["bool"]


def test_query_with_keywords_kind_and_vector():
    query = build_match_query("emma", EMMA, q="kserve", kind="speaker", vector=[0.1, 0.2])
    inner = query["script_score"]["query"]
    assert inner["bool"]["must"][0]["multi_match"]["query"] == "kserve"
    assert inner["bool"]["filter"] == [{"term": {"kind": "speaker"}}]
    assert query["script_score"]["script"]["params"]["v"] == [0.1, 0.2]


def test_filters_are_exact_terms_and_company_covers_past():
    assert build_filters({"school": "University of Utah", "city": "", "country": None}) == [
        {"term": {"schools": "University of Utah"}}
    ]
    assert build_filters({"company": "Copperleaf"}) == [
        {
            "bool": {
                "should": [{"term": {"company": "Copperleaf"}}, {"term": {"past_companies": "Copperleaf"}}],
                "minimum_should_match": 1,
            }
        }
    ]


def test_groups_follow_the_users_values_and_drop_empty_buckets():
    aggs = build_group_aggs(EMMA)
    assert set(aggs) == {"schools", "companies", "communities", "city", "country"}
    assert list(aggs["companies"]["filters"]["filters"]) == ["Wasatch Cloud", "Copperleaf"]
    response = {
        "schools": {"buckets": {"University of Utah": {"doc_count": 7}}},
        "companies": {"buckets": {"Wasatch Cloud": {"doc_count": 24}, "Copperleaf": {"doc_count": 0}}},
        "city": {"buckets": {"Salt Lake City": {"doc_count": 9}}},
    }
    groups = parse_groups(EMMA, response)
    assert groups["schools"] == [{"key": "University of Utah", "count": 7}]
    assert groups["companies"] == [{"key": "Wasatch Cloud", "count": 24}]
    assert groups["communities"] == [] and groups["country"] == []
