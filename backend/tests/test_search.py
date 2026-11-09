"""Search request building and the keyword fallback, without Elasticsearch or OpenAI."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import embeddings, load
from app.main import app
from app.routers import search as s

AT = datetime(2026, 11, 9, 8, 40)
VEC = [0.1, 0.2, 0.3]


@pytest.fixture
def no_key(monkeypatch):
    monkeypatch.setattr(embeddings.settings, "openai_api_key", "")


@pytest.fixture
def with_key(monkeypatch):
    monkeypatch.setattr(embeddings.settings, "openai_api_key", "test-key-not-real")


def test_bm25_body_is_multi_match_with_filters():
    p = s.SearchParams(q="gpu inference", kind=["talk", "keynote"], day=["2026-11-10"])
    body = s.results_body(p, AT, None)
    assert "retriever" not in body
    mm = body["query"]["bool"]["must"][0]["multi_match"]
    assert mm["query"] == "gpu inference"
    assert mm["fields"] == ["title^3", "speaker_names^2", "projects^2", "track", "description"]
    assert {"terms": {"kind": ["talk", "keynote"]}} in body["query"]["bool"]["filter"]
    assert {"terms": {"day": ["2026-11-10"]}} in body["query"]["bool"]["filter"]
    assert body["_source"] == {"excludes": ["embedding"]}


def test_hybrid_body_fuses_bm25_and_knn_with_rrf_and_filters_both():
    p = s.SearchParams(q="gpu inference", track=["AI Inference + Agentic"], upcoming=True, size=10)
    rrf = s.results_body(p, AT, VEC)["retriever"]["rrf"]
    standard, knn = rrf["retrievers"][0]["standard"], rrf["retrievers"][1]["knn"]
    assert rrf["rank_window_size"] == 50
    assert knn["query_vector"] == VEC and knn["field"] == "embedding"
    assert knn["k"] == 20 and knn["num_candidates"] == 100
    upcoming = {"range": {"ends_at": {"gt": "2026-11-09T08:40:00"}}}
    for flt in (standard["query"]["bool"]["filter"], knn["filter"]):
        assert {"terms": {"track": ["AI Inference + Agentic"]}} in flt
        assert upcoming in flt


def test_no_query_lists_by_start_time():
    body = s.results_body(s.SearchParams(day=["2026-11-10"], kind=["keynote"]), AT, None)
    assert body["sort"][0] == {"starts_at": "asc"}
    assert body["query"] == {"bool": {"filter": [{"terms": {"day": ["2026-11-10"]}}, {"terms": {"kind": ["keynote"]}}]}}


def test_each_facet_ignores_its_own_filter():
    p = s.SearchParams(q="otel", day=["2026-11-10"], kind=["talk"], upcoming=True)
    body = s.facets_body(p, AT, None)
    assert body["size"] == 0
    assert body["query"]["bool"]["filter"] == [{"range": {"ends_at": {"gt": "2026-11-09T08:40:00"}}}]
    assert body["aggs"]["day"]["filter"]["bool"]["filter"] == [{"terms": {"kind": ["talk"]}}]
    assert body["aggs"]["kind"]["filter"]["bool"]["filter"] == [{"terms": {"day": ["2026-11-10"]}}]
    assert len(body["aggs"]["track"]["filter"]["bool"]["filter"]) == 2


def test_hybrid_facets_count_knn_neighbours_too():
    should = s.facets_body(s.SearchParams(q="otel"), AT, VEC)["query"]["bool"]["should"]
    assert "multi_match" in should[0] and should[1]["knn"]["query_vector"] == VEC


def test_hits_drop_embedding_and_truncate_description():
    hit = {"_id": "42", "_score": 1.5, "_source": {"title": "T", "description": "word " * 200, "embedding": VEC}}
    doc = s.shape_hit(hit)
    assert "embedding" not in doc
    assert len(doc["description"]) <= 400 and doc["description"].endswith("...")
    assert doc["id"] == "42" and doc["score"] == 1.5


def test_mode_falls_back_to_bm25(no_key):
    assert s.choose_mode("hybrid", "gpu") == "bm25"


def test_mode_hybrid_needs_query_and_key(with_key):
    assert s.choose_mode("hybrid", "gpu") == "hybrid"
    assert s.choose_mode("hybrid", "") == "bm25"
    assert s.choose_mode("bm25", "gpu") == "bm25"


class FakeES:
    def __init__(self):
        self.searches = None

    def msearch(self, searches):
        self.searches = searches
        hit = {"_id": "1", "_score": 2.0, "_source": {"title": "GPU talk", "description": "short"}}
        buckets = {f: {"values": {"buckets": [{"key": "x", "doc_count": 1}]}} for f in s.FACETS}
        return {"responses": [{"hits": {"total": {"value": 1}, "hits": [hit]}}, {"aggregations": buckets}]}


def test_endpoint_without_key_is_keyword_only(no_key, monkeypatch):
    fake = FakeES()
    monkeypatch.setattr(s, "es", fake)
    monkeypatch.setattr(embeddings, "_client", lambda: pytest.fail("OpenAI must not be called"))
    r = TestClient(app).get("/api/search", params={"q": "gpu", "kind": ["talk", "keynote"], "size": 500})
    body = r.json()
    assert r.status_code == 200
    assert body["mode"] == "bm25" and body["total"] == 1
    assert body["results"][0] == {"title": "GPU talk", "description": "short", "id": "1", "score": 2.0}
    assert body["facets"]["kind"] == [{"key": "x", "count": 1}]
    sent = fake.searches[1]
    assert "retriever" not in sent and sent["size"] == 50
    assert {"terms": {"kind": ["talk", "keynote"]}} in sent["query"]["bool"]["filter"]


def test_bad_day_is_rejected():
    assert TestClient(app).get("/api/search", params={"day": "monday"}).status_code == 422


def test_embed_is_skipped_without_key(no_key):
    assert embeddings.embed(["anything"]) == []
    docs = [{"id": "1", "title": "T"}]
    assert load.with_embeddings(docs, load.session_text) == docs


def test_embedding_text_is_trimmed():
    text = load.session_text({"title": "T", "track": "AI", "projects": ["vLLM", "KServe"], "description": "x" * 5000})
    assert text.startswith("T\nAI\nvLLM, KServe\n") and len(text) == embeddings.EMBED_CHARS


def test_embedding_cost():
    assert embeddings.cost_usd("text-embedding-3-small", 1_000_000) == pytest.approx(0.02)


def _hit(i: str) -> dict:
    return {"_id": i, "_score": 9.0, "_source": {"title": i}}


def test_rrf_fuse_rewards_documents_in_both_lists():
    fused = s.rrf_fuse([[_hit("a"), _hit("b"), _hit("c")], [_hit("c"), _hit("d")]], size=4)
    assert [h["_id"] for h in fused] == ["c", "a", "b", "d"]  # b and d tie at 1/62: first seen wins
    assert fused[0]["_score"] == pytest.approx(1 / 63 + 1 / 61)
    assert fused[1]["_score"] == pytest.approx(1 / 61)


def test_rrf_fuse_only_counts_the_rank_window():
    long = [_hit(str(i)) for i in range(80)]
    fused = s.rrf_fuse([long], size=80, window=50)
    assert len(fused) == 50 and fused[-1]["_id"] == "49"


LICENSE_ERROR = {
    "type": "security_exception",
    "reason": "current license is non-compliant for [Reciprocal Rank Fusion (RRF)]",
    "license.expired.feature": "Reciprocal Rank Fusion (RRF)",
}


def test_license_errors_are_recognised():
    assert s.is_license_error(LICENSE_ERROR)
    assert s.is_license_error({"type": "security_exception", "reason": "rrf is not available"})
    assert not s.is_license_error({"type": "parsing_exception", "reason": "unknown field [foo]"})


class BasicLicenseES:
    """Rejects the rrf retriever the way a basic-licence cluster does; answers everything else."""

    def __init__(self):
        self.calls = []

    def msearch(self, searches):
        bodies = searches[1::2]
        self.calls.append(bodies)
        out = []
        for b in bodies:
            if "retriever" in b:
                out.append({"error": LICENSE_ERROR, "status": 403})
            elif "knn" in b:
                out.append({"hits": {"total": {"value": 2}, "hits": [_hit("k1"), _hit("both")]}})
            elif "aggs" in b:
                out.append({"aggregations": {}})
            else:
                out.append({"hits": {"total": {"value": 5}, "hits": [_hit("both"), _hit("b1")]}})
        return {"responses": out}


def test_basic_licence_falls_back_to_client_rrf_and_remembers(with_key, monkeypatch):
    fake = BasicLicenseES()
    monkeypatch.setattr(s, "es", fake)
    monkeypatch.setattr(s, "_native_rrf", None)
    monkeypatch.setattr(embeddings, "embed", lambda texts: [VEC])
    client = TestClient(app)

    body = client.get("/api/search", params={"q": "gpu"}).json()
    assert body["mode"] == "hybrid-client"
    assert [r["id"] for r in body["results"]] == ["both", "k1", "b1"]
    assert body["total"] == 5
    assert len(fake.calls) == 2  # the rejected native call, then BM25 + kNN + facets
    assert s._native_rrf is False

    assert client.get("/api/search", params={"q": "gpu"}).json()["mode"] == "hybrid-client"
    assert len(fake.calls) == 3 and not any("retriever" in b for b in fake.calls[2])


def test_other_search_errors_are_not_swallowed(with_key, monkeypatch):
    class Broken(BasicLicenseES):
        def msearch(self, searches):
            return {"responses": [{"error": {"type": "parsing_exception", "reason": "bad"}}, {}]}

    monkeypatch.setattr(s, "es", Broken())
    monkeypatch.setattr(s, "_native_rrf", None)
    monkeypatch.setattr(embeddings, "embed", lambda texts: [VEC])
    with pytest.raises(s.SearchFailed):
        TestClient(app).get("/api/search", params={"q": "gpu"})
    assert s._native_rrf is None
