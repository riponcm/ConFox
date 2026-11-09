"""Pure parts of People Match: reasons, query building and group parsing. No Elasticsearch needed."""

import pytest

from app.routers import people as pp
from app.routers.people import (
    BOOST,
    RRF_K,
    RRF_WEIGHT,
    affinity,
    build_filters,
    build_group_aggs,
    build_match_query,
    knn_clause,
    match_body,
    parse_groups,
    rank_people,
    related_topics,
    rerank,
    topics,
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
    assert query["bool"]["must_not"] == [{"ids": {"values": ["emma"]}}, {"term": {"visibility": "private"}}]
    assert ({"terms": {"country": ["United States"]}}, BOOST["country"]) in boosts
    assert query["bool"]["minimum_should_match"] == 0
    assert "must" not in query["bool"] and "filter" not in query["bool"]


def test_query_with_keywords_and_kind():
    query = build_match_query("emma", EMMA, q="kserve", kind="speaker")
    assert query["bool"]["must"][0]["multi_match"]["query"] == "kserve"
    assert query["bool"]["filter"] == [{"term": {"kind": "speaker"}}]


def test_topics_join_interests_projects_and_tracks_without_case_repeats():
    user = {"interests": ["eBPF", "GitOps"], "projects": ["Cilium", "ebpf"], "tracks": ["Security"]}
    assert topics(user) == ["eBPF", "GitOps", "Cilium", "Security"]
    assert topics({}) == []


def test_profile_topics_drive_boosts_and_reasons():
    emma = EMMA | {"interests": ["eBPF"], "schools": ["University of Utah", "BUET"], "projects": ["Cilium"]}
    buet = {"kind": "attendee", "interests": ["eBPF", "Cilium"], "schools": ["Georgia Tech", "BUET"], "city": "Tokyo"}
    query = build_match_query("emma", emma)
    assert ({"terms": {"schools": ["BUET"]}}, BOOST["schools"]) in _constant_scores(query)
    assert ({"terms": {"interests": ["Cilium"]}}, BOOST["interests"]) in _constant_scores(query)
    assert why(emma, buet) == [
        {"label": "BUET alumni", "field": "schools", "value": "BUET"},
        {"label": "Both into eBPF", "field": "interests", "value": "eBPF"},
        {"label": "Both into Cilium", "field": "interests", "value": "Cilium"},
    ]
    assert affinity(emma, buet) == BOOST["schools"] + 2 * BOOST["interests"]


def test_country_reason_only_when_the_city_differs():
    person = {"city": "Austin", "country": "United States"}
    assert why(EMMA, person) == [{"label": "Also from United States", "field": "country", "value": "United States"}]
    assert affinity(EMMA, person) == BOOST["country"]
    same_city = {"city": "Salt Lake City", "country": "United States"}
    assert [w["field"] for w in why(EMMA, same_city)] == ["city"]
    assert affinity(EMMA, same_city) == BOOST["city"] + BOOST["country"]


def test_speakers_sharing_a_chosen_track_speak_on_it():
    speaker = {"kind": "speaker", "interests": ["Security"]}
    assert why(EMMA | {"tracks": ["Security"]}, speaker) == [
        {"label": "Speaks on Security", "field": "interests", "value": "Security"}
    ]


VEC = [0.1, 0.2]


def test_hybrid_body_fuses_lexical_and_knn_with_the_same_filters():
    post = build_filters({"school": "BUET"})
    body = match_body("emma", EMMA, VEC, q="cilium", kind="attendee", post=post, aggs={"a": {}})
    rrf = body["retriever"]["rrf"]
    assert rrf["rank_constant"] == RRF_K and rrf["rank_window_size"] == body["size"]
    standard, knn = (r for r in rrf["retrievers"])
    assert standard["standard"]["query"] == build_match_query("emma", EMMA, "cilium", "attendee")
    flt = knn["knn"]["filter"]
    assert knn["knn"]["query_vector"] == VEC
    assert {"bool": {"must_not": [{"ids": {"values": ["emma"]}}, {"term": {"visibility": "private"}}]}} in flt
    assert {"term": {"kind": "attendee"}} in flt and {"term": {"schools": "BUET"}} in flt
    assert any("multi_match" in f for f in flt)  # a keyword narrows the semantic side too
    assert body["post_filter"] == {"bool": {"filter": post}} and body["aggs"] == {"a": {}}
    assert body["_source"] == {"excludes": ["embedding"]}


def test_lexical_body_without_vector():
    body = match_body("emma", EMMA)
    assert "retriever" not in body and body["query"] == build_match_query("emma", EMMA)
    assert "post_filter" not in body and "aggs" not in body


def test_knn_clause_without_keyword_or_kind():
    clause = knn_clause("emma", VEC)
    assert len(clause["filter"]) == 1 and clause["k"] == pp.RANK_WINDOW


def _hit(pid: str, score: float, **src) -> dict:
    return {"_id": pid, "_score": score, "_source": {"name": pid, **src}}


def test_rerank_adds_boosts_on_top_of_the_fused_rank():
    top = 2 / (RRF_K + 1)  # first in both lists
    fused = [_hit("near", top), _hit("alum", 1 / (RRF_K + 50), schools=["University of Utah"])]
    ranked = rerank(EMMA, fused, lists=2, size=10)
    assert [p["id"] for p in ranked] == ["alum", "near"]  # one shared school beats any embedding
    assert ranked[1]["score"] == RRF_WEIGHT and ranked[1]["why"] == []
    assert ranked[0]["affinity"] == BOOST["schools"]
    assert ranked[0]["why"][0]["label"] == "University of Utah alumni"
    assert "_score" not in ranked[0] and "embedding" not in ranked[0]
    assert len(rerank(EMMA, fused, lists=2, size=1)) == 1


class FakePeopleES:
    """msearch stand-in. `native` is how a body with a retriever answers: 'ok', 'licence' or 'broken'."""

    def __init__(self, native: str = "ok"):
        self.native = native
        self.calls: list[list[dict]] = []

    def msearch(self, searches):
        bodies = searches[1::2]
        self.calls.append(bodies)
        out = []
        for b in bodies:
            if "retriever" in b and self.native == "licence":
                out.append(
                    {"error": {"type": "security_exception", "reason": "current license is non-compliant for [rrf]"}}
                )
            elif "retriever" in b and self.native == "broken":
                out.append({"error": {"type": "illegal_argument_exception", "reason": "no embedding field"}})
            elif "knn" in b:
                out.append({"hits": {"hits": [_hit("k1", 0.9), _hit("both", 0.8)]}})
            else:
                hits = [_hit("both", 3.0), _hit("alum", 2.0, schools=["University of Utah"])]
                out.append({"hits": {"hits": hits}, "aggregations": {"schools": {}}})
        return {"responses": out}


@pytest.mark.parametrize(
    ("native", "mode", "calls"),
    [("ok", "hybrid", 1), ("licence", "hybrid-client", 2), ("broken", "bm25", 2)],
)
def test_rank_people_modes(monkeypatch, native, mode, calls):
    fake = FakePeopleES(native)
    monkeypatch.setattr(pp, "es", fake)
    monkeypatch.setattr(pp, "_native_rrf", None)
    ranked, aggs, used = rank_people("emma", EMMA, VEC, size=5)
    assert used == mode and len(fake.calls) == calls
    assert ranked[0]["id"] == "alum"  # the shared school wins in every mode
    if mode == "hybrid-client":
        assert pp._native_rrf is False and {r["id"] for r in ranked} == {"alum", "both", "k1"}
        rank_people("emma", EMMA, VEC)  # remembered: no second native attempt
        assert not any("retriever" in b for b in fake.calls[-1])
    if mode == "bm25":
        assert not any("knn" in b for b in fake.calls[-1])


def test_rank_people_without_vector_is_lexical(monkeypatch):
    fake = FakePeopleES()
    monkeypatch.setattr(pp, "es", fake)
    ranked, aggs, used = rank_people("emma", EMMA, None)
    assert used == "bm25" and len(fake.calls) == 1 and aggs == {"schools": {}}
    assert [r["id"] for r in ranked] == ["alum", "both"]


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
