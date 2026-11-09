"""Session search: keyword (BM25) and hybrid (BM25 plus kNN on embeddings, fused with reciprocal rank fusion).

The request bodies and the fusion are pure functions so they can be tested without Elasticsearch. One `msearch`
call returns both the results and the facets. Native RRF (the `rrf` retriever) needs an Enterprise or trial
licence; on a basic licence the BM25 and kNN lists are fetched separately and fused here ("hybrid-client").
"""

import logging
import re
import time
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Annotated, Literal

from elasticsearch import ApiError
from fastapi import APIRouter, HTTPException, Query
from opentelemetry import metrics, trace

from .. import activity, embeddings
from ..clock import now
from ..config import settings
from ..es import es

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["search"])
meter = metrics.get_meter("confox.search")
DURATION = meter.create_histogram("confox.search.duration", unit="ms", description="Search time, embedding included")
REQUESTS = meter.create_counter("confox.search.requests", unit="{request}", description="Search requests")

Mode = Literal["hybrid", "bm25"]  # what the caller asks for
Used = Literal["hybrid", "hybrid-client", "bm25"]  # what actually ran
Many = Annotated[list[str], Query()]  # repeatable: ?kind=talk&kind=keynote
FACETS = ("day", "kind", "track", "level")
TEXT_FIELDS = ["title^3", "speaker_names^2", "projects^2", "track", "description"]
MAX_SIZE = 50
RANK_WINDOW = 50
NUM_CANDIDATES = 100
DESCRIPTION_CHARS = 400
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RRF_K = 60

# Whether this cluster accepts the native rrf retriever (it needs an Enterprise or trial licence). None until the
# first hybrid search finds out; then kept for the process lifetime so failing calls are not repeated.
_native_rrf: bool | None = None


@dataclass
class SearchParams:
    q: str = ""
    day: list[str] = field(default_factory=list)
    kind: list[str] = field(default_factory=list)
    track: list[str] = field(default_factory=list)
    level: list[str] = field(default_factory=list)
    upcoming: bool = False
    size: int = 20

    def facet_values(self, name: str) -> list[str]:
        return getattr(self, name)


def facet_filters(p: SearchParams, skip: str | None = None) -> list[dict]:
    """Term filters for the chosen facet values; `skip` leaves out one facet's own filter (for its counts)."""
    return [{"terms": {f: p.facet_values(f)}} for f in FACETS if f != skip and p.facet_values(f)]


def time_filters(p: SearchParams, at: datetime) -> list[dict]:
    if not p.upcoming:
        return []
    return [{"range": {"ends_at": {"gt": at.strftime("%Y-%m-%dT%H:%M:%S")}}}]


def filters(p: SearchParams, at: datetime) -> list[dict]:
    return facet_filters(p) + time_filters(p, at)


def text_query(q: str) -> dict:
    return {"multi_match": {"query": q, "fields": TEXT_FIELDS}}


def knn(vector: list[float], k: int, flt: list[dict]) -> dict:
    """kNN clause; filters are applied while searching the graph, so k results survive the filters."""
    clause = {"field": "embedding", "query_vector": vector, "k": k, "num_candidates": max(NUM_CANDIDATES, k)}
    if flt:
        clause["filter"] = flt
    return clause


def results_body(p: SearchParams, at: datetime, vector: list[float] | None) -> dict:
    """The request for the result list: hybrid when there is a query vector, BM25 with text, else by start time."""
    flt = filters(p, at)
    body: dict = {"size": p.size, "_source": {"excludes": ["embedding"]}, "track_total_hits": True}
    if not p.q:
        body["query"] = {"bool": {"filter": flt}}
        body["sort"] = [{"starts_at": "asc"}, {"title.raw": "asc"}]
        return body
    lexical = {"bool": {"must": [text_query(p.q)], "filter": flt}}
    if vector is None:
        body["query"] = lexical
        return body
    body["retriever"] = {
        "rrf": {
            "retrievers": [{"standard": {"query": lexical}}, {"knn": knn(vector, p.size * 2, flt)}],
            "rank_window_size": max(RANK_WINDOW, p.size),
            "rank_constant": RRF_K,
        }
    }
    return body


def facets_body(p: SearchParams, at: datetime, vector: list[float] | None) -> dict:
    """Facet counts over the same matches as the results, each facet ignoring its own filter.

    So picking Tuesday still shows how many matches every other day has. In hybrid mode the match set is the
    BM25 matches plus the kNN neighbours, as in the fused result list.
    """
    should = []
    if p.q:
        should.append(text_query(p.q))
        if vector is not None:
            should.append({"knn": knn(vector, p.size * 2, [])})
    base: dict = {"bool": {"filter": time_filters(p, at)}}
    if should:
        base["bool"] |= {"should": should, "minimum_should_match": 1}
    aggs = {
        f: {
            "filter": {"bool": {"filter": facet_filters(p, skip=f)}},
            "aggs": {"values": {"terms": {"field": f, "size": 60}}},
        }
        for f in FACETS
    }
    return {"size": 0, "query": base, "aggs": aggs}


def shape_hit(hit: dict) -> dict:
    doc = {k: v for k, v in hit["_source"].items() if k != "embedding"}
    desc = doc.get("description") or ""
    if len(desc) > DESCRIPTION_CHARS:
        cut = desc[: DESCRIPTION_CHARS - 3]
        doc["description"] = (cut.rsplit(" ", 1)[0] if " " in cut else cut).rstrip() + "..."
    return doc | {"id": hit["_id"], "score": hit.get("_score")}


def shape_facets(aggs: dict) -> dict[str, list[dict]]:
    return {
        f: [{"key": b["key"], "count": b["doc_count"]} for b in aggs[f]["values"]["buckets"]]
        for f in FACETS
        if f in aggs
    }


def choose_mode(requested: Mode, q: str) -> Mode:
    """Hybrid needs both a query and an embedding key; otherwise keyword only."""
    return "hybrid" if requested == "hybrid" and q and embeddings.enabled() else "bm25"


def knn_body(p: SearchParams, at: datetime, vector: list[float]) -> dict:
    """The kNN side on its own, for client-side fusion."""
    k = p.size * 2
    return {"size": k, "knn": knn(vector, k, filters(p, at)), "_source": {"excludes": ["embedding"]}}


def rrf_fuse(rankings: list[list[dict]], size: int, k: int = RRF_K, window: int = RANK_WINDOW) -> list[dict]:
    """Reciprocal rank fusion, as Elasticsearch's rrf retriever does it: each list contributes 1 / (k + rank) for
    the documents in its top `window`. Returns the top `size` hits with `_score` set to the fused score."""
    scores: dict[str, float] = {}
    hits: dict[str, dict] = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking[:window], start=1):
            scores[hit["_id"]] = scores.get(hit["_id"], 0.0) + 1 / (k + rank)
            hits.setdefault(hit["_id"], hit)
    order = sorted(scores, key=lambda i: -scores[i])  # stable: ties keep first-seen order
    return [hits[i] | {"_score": scores[i]} for i in order[:size]]


def is_license_error(error: object) -> bool:
    """True for the error a basic-licence cluster returns for the rrf retriever (a security exception naming RRF)."""
    text = str(error).lower()
    return "license" in text or ("security_exception" in text and "rrf" in text)


class SearchFailed(Exception):
    """One body inside an msearch failed; `error` is Elasticsearch's error object for it."""

    def __init__(self, error: dict):
        super().__init__(f"search failed: {error}")
        self.error = error


def _msearch(bodies: list[dict]) -> list[dict]:
    searches = [part for body in bodies for part in ({"index": settings.idx_sessions}, body)]
    responses = es.msearch(searches=searches)["responses"]
    for r in responses:
        if "error" in r:
            raise SearchFailed(r["error"])
    return responses


def _native_failed(exc: Exception) -> bool:
    detail = exc.error if isinstance(exc, SearchFailed) else getattr(exc, "body", None)
    return is_license_error(detail) or is_license_error(exc)


def run(p: SearchParams, mode: Mode, at: datetime) -> tuple[Used, dict, dict]:
    global _native_rrf
    vector = None
    if mode == "hybrid":
        try:
            vector = embeddings.embed([p.q])[0]
        except Exception as exc:
            log.warning("query embedding failed, falling back to keyword search: %s", exc, exc_info=exc)
            trace.get_current_span().record_exception(exc)
    if vector is None:
        results, facets = _msearch([results_body(p, at, None), facets_body(p, at, None)])
        return "bm25", results, facets

    facets_req = facets_body(p, at, vector)
    if _native_rrf is not False:
        try:
            results, facets = _msearch([results_body(p, at, vector), facets_req])
            _native_rrf = True
            return "hybrid", results, facets
        except (ApiError, SearchFailed) as exc:
            if not _native_failed(exc):
                raise
            _native_rrf = False
            log.warning("native rrf retriever not licensed on this cluster; using client-side RRF from now on: %s", exc)
            span = trace.get_current_span()
            span.record_exception(exc)
            span.add_event("confox.search.rrf_fallback", {"reason": str(exc)[:500]})

    window = replace(p, size=max(RANK_WINDOW, p.size))
    lexical, neighbours, facets = _msearch([results_body(window, at, None), knn_body(p, at, vector), facets_req])
    ranked = [lexical["hits"]["hits"], neighbours["hits"]["hits"]]
    seen = {h["_id"] for hits in ranked for h in hits}
    # Approximate: BM25 matches plus any kNN neighbours that BM25 did not return in its window.
    total = max(lexical["hits"]["total"]["value"], len(seen))
    return "hybrid-client", {"hits": {"total": {"value": total}, "hits": rrf_fuse(ranked, p.size)}}, facets


@router.get("")
def search(
    q: str = "",
    day: Many = (),
    kind: Many = (),
    track: Many = (),
    level: Many = (),
    upcoming: bool = False,
    mode: Mode = "hybrid",
    size: int = 20,
) -> dict:
    """Search sessions. With no `q`, sessions matching the filters in start-time order."""
    started = time.perf_counter()
    if bad := [d for d in day if not DAY.match(d)]:
        raise HTTPException(status_code=422, detail=f"day must be YYYY-MM-DD, got {bad[0]!r}")
    p = SearchParams(
        q=q.strip(),
        day=list(day),
        kind=list(kind),
        track=list(track),
        level=list(level),
        upcoming=upcoming,
        size=min(max(size, 1), MAX_SIZE),
    )
    used, results, facets = run(p, choose_mode(mode, p.q), now())

    took_ms = round((time.perf_counter() - started) * 1000)
    span = trace.get_current_span()
    span.set_attribute("confox.search.mode", used)
    span.set_attribute("confox.search.total", results["hits"]["total"]["value"])
    DURATION.record(took_ms, {"mode": used})
    REQUESTS.add(1, {"mode": used})
    if p.q:
        activity.record("search", settings.demo_user, p.q)
    return {
        "mode": used,
        "took_ms": took_ms,
        "total": results["hits"]["total"]["value"],
        "results": [shape_hit(h) for h in results["hits"]["hits"]],
        "facets": shape_facets(facets.get("aggregations", {})),
    }
