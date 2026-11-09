"""People: profiles and Match.

Match ranks other people for the signed-in user, read fresh from Elasticsearch on every request, so a profile
edit changes the next ranking. The pipeline:

1. Candidates and relevance: reciprocal rank fusion of a lexical list (BM25 of the user's topics on
   `interests_text` and `bio`, plus a fixed boost per shared value) and a semantic list (kNN on the profile
   `embedding`). Native `rrf` retriever when the licence allows it, else the same fusion in Python.
2. Boosts: the fused score is scaled to at most RRF_WEIGHT and the shared-value boosts are added on top, so a
   shared school always outranks a close embedding.
3. Reasons: `why` is computed in Python from the same overlap the boosts count, so every reason is true.
"""

import logging

from elasticsearch import ApiError, NotFoundError
from fastapi import APIRouter, HTTPException
from opentelemetry import metrics, trace

from .. import activity
from ..config import settings
from ..es import es
from .search import SearchFailed, is_license_error, rrf_fuse

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/people", tags=["people"])
match_requests = metrics.get_meter("confox.people").create_counter(
    "confox.match.requests", unit="{request}", description="People Match requests"
)

# Fixed boosts per shared value. Schools weigh most: alumni ties are the demo's headline reason.
BOOST = {"schools": 6.0, "company": 3.0, "communities": 2.0, "city": 2.0, "country": 1.0, "interests": 1.5}
RELATED_BOOST = 0.5  # soft text match of the user's topics, so speakers (track names) still rank by topic
RRF_WEIGHT = 4.0  # the fused rank adds at most this; below one shared school by design
RRF_K = 60
RANK_WINDOW = 100
NUM_CANDIDATES = 200
MAX_REASONS = 3
TEXT_FIELDS = ["name^3", "title^2", "company^2", "interests_text^2", "bio"]
SOURCE_EXCLUDES = ["embedding"]
PRIVATE = {"term": {"visibility": "private"}}

# Query parameter -> indexed field(s). `company` matches the current or a past company.
FILTER_FIELDS: dict[str, list[str]] = {
    "school": ["schools"],
    "company": ["company", "past_companies"],
    "community": ["communities"],
    "interest": ["interests"],
    "country": ["country"],
    "city": ["city"],
    "kind": ["kind"],
}
GROUPS = ["schools", "companies", "communities", "city", "country"]

# Whether this cluster accepts the native rrf retriever; None until the first hybrid match finds out.
_native_rrf: bool | None = None


def _values(doc: dict, field: str) -> list[str]:
    v = doc.get(field)
    if v is None or v == "":
        return []
    return [x for x in v if x] if isinstance(v, list) else [v]


def companies(doc: dict) -> list[str]:
    """Current company first, then past companies, without duplicates."""
    return list(dict.fromkeys(_values(doc, "company") + _values(doc, "past_companies")))


def topics(user: dict) -> list[str]:
    """What the user is into: interests, then keywords or projects, then chosen tracks, without duplicates
    (ignoring case). Other people's `interests` hold all three kinds (attendees list projects there, speakers
    their session tracks), so each topic is matched against that one field."""
    seen: set[str] = set()
    out = []
    for v in _values(user, "interests") + _values(user, "projects") + _values(user, "tracks"):
        if v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)
    return out


def group_values(user: dict) -> dict[str, list[str]]:
    """The user's own values per group; groups and boosts are restricted to these."""
    return {
        "schools": _values(user, "schools"),
        "companies": companies(user),
        "communities": _values(user, "communities"),
        "city": _values(user, "city"),
        "country": _values(user, "country"),
    }


def _shared(mine: list[str], theirs: list[str]) -> list[str]:
    their_set = set(theirs)
    return [v for v in mine if v in their_set]


def affinity(user: dict, person: dict) -> float:
    """The fixed boosts for what two people share; the same table the lexical query uses."""
    score = BOOST["schools"] * len(_shared(_values(user, "schools"), _values(person, "schools")))
    score += BOOST["company"] if _shared(companies(user), companies(person)) else 0.0
    score += BOOST["communities"] * len(_shared(_values(user, "communities"), _values(person, "communities")))
    score += BOOST["city"] if _shared(_values(user, "city"), _values(person, "city")) else 0.0
    score += BOOST["country"] if _shared(_values(user, "country"), _values(person, "country")) else 0.0
    score += BOOST["interests"] * len(_shared(topics(user), _values(person, "interests")))
    return score


def why(user: dict, person: dict) -> list[dict]:
    """Up to three reasons, most telling first.

    Order: schools, the first shared topic, company, community, city (or country when the city differs), further
    topics, related topics, then topics named in the bio.
    """
    mine = topics(user)
    shared = _shared(mine, _values(person, "interests"))
    verb = "Speaks on" if person.get("kind") == "speaker" else "Both into"
    reasons = [
        {"label": f"{v} alumni", "field": "schools", "value": v}
        for v in _shared(_values(user, "schools"), _values(person, "schools"))
    ]
    reasons += [{"label": f"{verb} {v}", "field": "interests", "value": v} for v in shared[:1]]
    for v in _shared(companies(user), companies(person)):
        label = "Works at" if v == person.get("company") else "Worked at"
        reasons.append({"label": f"{label} {v}", "field": "company", "value": v})
    reasons += [
        {"label": f"Both in {v}", "field": "communities", "value": v}
        for v in _shared(_values(user, "communities"), _values(person, "communities"))
    ]
    city = _shared(_values(user, "city"), _values(person, "city"))
    reasons += [{"label": f"Also in {v}", "field": "city", "value": v} for v in city]
    if not city:
        reasons += [
            {"label": f"Also from {v}", "field": "country", "value": v}
            for v in _shared(_values(user, "country"), _values(person, "country"))
        ]
    reasons += [{"label": f"{verb} {v}", "field": "interests", "value": v} for v in shared[1:]]
    verb = "Speaks on" if person.get("kind") == "speaker" else "Into"
    reasons += [{"label": f"{verb} {v}", "field": "interests", "value": v} for v in related_topics(user, person)]
    bio = (person.get("bio") or "").lower()
    named = [u for u in mine if u not in shared and u.lower() in bio]
    reasons += [{"label": f"Mentions {v}", "field": "q", "value": v} for v in named]  # field q: a keyword search
    return reasons[:MAX_REASONS]


def related_topics(user: dict, person: dict) -> list[str]:
    """The person's topics that contain, or are contained in, one of the user's topics, ignoring case.

    Speakers' interests are session tracks ("AI Inference + Agentic"), which rarely equal an attendee interest
    ("AI inference") exactly. The person's own value is returned, so it works as an exact filter.
    """
    mine = [u.lower() for u in topics(user)]
    return [
        p
        for p in _values(person, "interests")
        if p.lower() not in mine and any(u in p.lower() or p.lower() in u for u in mine)
    ]


def _boost(field: str | list[str], values: list[str], boost: float) -> dict:
    fields = field if isinstance(field, list) else [field]
    clauses = [{"terms": {f: values}} for f in fields]
    flt = clauses[0] if len(clauses) == 1 else {"bool": {"should": clauses, "minimum_should_match": 1}}
    return {"constant_score": {"filter": flt, "boost": boost}}


def build_filters(filters: dict[str, str | None]) -> list[dict]:
    """Exact term filters from query parameters; empty values are ignored."""
    out = []
    for param, value in filters.items():
        if not value:
            continue
        fields = FILTER_FIELDS[param]
        clauses = [{"term": {f: value}} for f in fields]
        out.append(clauses[0] if len(clauses) == 1 else {"bool": {"should": clauses, "minimum_should_match": 1}})
    return out


def keyword_query(q: str) -> dict:
    return {"multi_match": {"query": q, "fields": TEXT_FIELDS, "fuzziness": "AUTO"}}


def build_match_query(user_id: str, user: dict, q: str = "", kind: str | None = None) -> dict:
    """The lexical side: a fixed boost per shared value plus BM25 of the user's topics, optionally a keyword match.

    Every candidate matches (minimum_should_match 0), so people with nothing in common still appear, just lower.
    The user and anyone who set their profile to private are left out.
    """
    should = []
    for v in _values(user, "schools"):
        should.append(_boost("schools", [v], BOOST["schools"]))
    if mine := companies(user):  # one boost for any shared employer, however many overlap
        should.append(_boost(["company", "past_companies"], mine, BOOST["company"]))
    for v in _values(user, "communities"):
        should.append(_boost("communities", [v], BOOST["communities"]))
    if city := _values(user, "city"):
        should.append(_boost("city", city, BOOST["city"]))
    if country := _values(user, "country"):
        should.append(_boost("country", country, BOOST["country"]))
    mine = topics(user)
    for v in mine:
        should.append(_boost("interests", [v], BOOST["interests"]))
    if mine:
        should.append(
            {"multi_match": {"query": " ".join(mine), "fields": ["interests_text", "bio"], "boost": RELATED_BOOST}}
        )

    query: dict = {
        "bool": {
            "must_not": [{"ids": {"values": [user_id]}}, PRIVATE],
            "should": should,
            "minimum_should_match": 0,
        }
    }
    if q:
        query["bool"]["must"] = [keyword_query(q)]
    if kind:
        query["bool"]["filter"] = build_filters({"kind": kind})
    return query


def knn_clause(
    user_id: str, vector: list[float], q: str = "", kind: str | None = None, post: list | None = None
) -> dict:
    """The semantic side: the people nearest the profile vector, under the same filters as the lexical side.

    Filters apply while the graph is searched, so `k` neighbours survive them; a keyword `q` becomes a filter too.
    """
    flt: list[dict] = [{"bool": {"must_not": [{"ids": {"values": [user_id]}}, PRIVATE]}}]
    if kind:
        flt += build_filters({"kind": kind})
    if q:
        flt.append(keyword_query(q))
    flt += post or []
    return {
        "field": "embedding",
        "query_vector": vector,
        "k": RANK_WINDOW,
        "num_candidates": NUM_CANDIDATES,
        "filter": flt,
    }


def match_body(
    user_id: str,
    user: dict,
    vector: list[float] | None = None,
    q: str = "",
    kind: str | None = None,
    post: list | None = None,
    aggs: dict | None = None,
) -> dict:
    """One search: the native rrf retriever over both sides when there is a vector, else the lexical query.

    Returns the whole rank window; `rerank` adds the boosts and cuts it to the page size. `post` filters go in
    post_filter, so the group counts in `aggs` stay stable while chips are toggled.
    """
    lexical = build_match_query(user_id, user, q, kind)
    body: dict = {"size": RANK_WINDOW, "_source": {"excludes": SOURCE_EXCLUDES}}
    if vector:
        body["retriever"] = {
            "rrf": {
                "retrievers": [
                    {"standard": {"query": lexical}},
                    {"knn": knn_clause(user_id, vector, q, kind, post)},
                ],
                "rank_window_size": RANK_WINDOW,
                "rank_constant": RRF_K,
            }
        }
    else:
        body["query"] = lexical
    if aggs:
        body["aggs"] = aggs
    if post:
        body["post_filter"] = {"bool": {"filter": post}}
    return body


def knn_body(user_id: str, vector: list[float], q: str = "", kind: str | None = None, post: list | None = None) -> dict:
    """The semantic side on its own, for client-side fusion."""
    return {
        "size": RANK_WINDOW,
        "knn": knn_clause(user_id, vector, q, kind, post),
        "_source": {"excludes": SOURCE_EXCLUDES},
    }


def rerank(user: dict, fused: list[dict], lists: int, size: int) -> list[dict]:
    """Final order: the shared-value boosts plus the fused rank scaled to at most RRF_WEIGHT.

    `fused` hits carry their RRF score in `_score`; the best possible is one first place per list, so dividing by
    lists / (RRF_K + 1) maps it to 0..1. Ties keep the fused order. Each hit gets `score`, `affinity` and `why`.
    """
    best = lists / (RRF_K + 1)
    out = []
    for hit in fused:
        person = _person(hit)
        rrf = float(hit.get("_score") or 0.0) / best if best else 0.0
        boost = affinity(user, person)
        out.append(
            person
            | {
                "score": round(boost + RRF_WEIGHT * min(rrf, 1.0), 3),
                "affinity": boost,
                "why": why(user, person),
            }
        )
    out.sort(key=lambda p: -p["score"])  # stable
    return out[:size]


def build_group_aggs(user: dict) -> dict:
    """One filters aggregation per group, with one bucket per value the user has."""
    aggs = {}
    for group, values in group_values(user).items():
        if not values:
            continue
        if group == "companies":
            buckets = {v: build_filters({"company": v})[0] for v in values}
        else:
            buckets = {v: {"term": {group: v}} for v in values}  # the other group names are the field names
        aggs[group] = {"filters": {"filters": buckets}}
    return aggs


def parse_groups(user: dict, aggs: dict) -> dict[str, list[dict]]:
    """Buckets in the user's own order, without empty ones."""
    out: dict[str, list[dict]] = {g: [] for g in GROUPS}
    for group, values in group_values(user).items():
        buckets = aggs.get(group, {}).get("buckets", {})
        for v in values:
            count = buckets.get(v, {}).get("doc_count", 0)
            if count:
                out[group].append({"key": v, "count": count})
    return out


def _load_user(user_id: str) -> tuple[dict, list | None]:
    """The user's profile as stored right now, and its embedding if there is one. Never cached: a profile edit
    must change the very next ranking. Elasticsearch 9 leaves vectors out of _source unless asked."""
    try:
        doc = es.get(index=settings.idx_people, id=user_id, source_exclude_vectors=False)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"unknown user {user_id}") from exc
    src = doc["_source"]
    vector = src.pop("embedding", None)
    return src, vector if isinstance(vector, list) and vector else None


def _person(hit: dict) -> dict:
    src = {k: v for k, v in hit["_source"].items() if k not in SOURCE_EXCLUDES}
    return {**src, "id": hit["_id"]}


def _msearch(bodies: list[dict]) -> list[dict]:
    searches = [part for body in bodies for part in ({"index": settings.idx_people}, body)]
    responses = es.msearch(searches=searches)["responses"]
    for r in responses:
        if "error" in r:
            raise SearchFailed(r["error"])
    return responses


def rank_people(
    user_id: str,
    user: dict,
    vector: list | None,
    q: str = "",
    kind: str | None = None,
    post: list | None = None,
    aggs: dict | None = None,
    size: int = 20,
) -> tuple[list[dict], dict, str]:
    """Ranked people (with score, affinity, why), the aggregations, and which mode ran:
    `hybrid` (native rrf retriever), `hybrid-client` (RRF in Python on a basic licence) or `bm25` (no vector,
    or vector search failed). Failures that change the mode are logged and recorded on the span."""
    global _native_rrf
    span = trace.get_current_span()
    if vector and _native_rrf is not False:
        try:
            (res,) = _msearch([match_body(user_id, user, vector, q, kind, post, aggs)])
            _native_rrf = True
            return rerank(user, res["hits"]["hits"], 2, size), res.get("aggregations", {}), "hybrid"
        except (ApiError, SearchFailed) as exc:
            detail = exc.error if isinstance(exc, SearchFailed) else getattr(exc, "body", None)
            if is_license_error(detail) or is_license_error(exc):
                _native_rrf = False
                log.warning("native rrf retriever not licensed; people match fuses in the API from now on: %s", exc)
                span.add_event("confox.match.rrf_fallback", {"reason": str(exc)[:500]})
            else:
                # The vector field may be missing or mid-rebuild; rank lexically rather than fail the page.
                log.warning("people match: vector search failed, ranking lexically: %s", exc, exc_info=exc)
                vector = None
            span.record_exception(exc)
    lexical_body = match_body(user_id, user, None, q, kind, post, aggs)
    if vector:
        try:
            lexical, neighbours = _msearch([lexical_body, knn_body(user_id, vector, q, kind, post)])
            fused = rrf_fuse([lexical["hits"]["hits"], neighbours["hits"]["hits"]], RANK_WINDOW, RRF_K, RANK_WINDOW)
            return rerank(user, fused, 2, size), lexical.get("aggregations", {}), "hybrid-client"
        except (ApiError, SearchFailed) as exc:
            log.warning("people match: kNN failed, ranking lexically: %s", exc, exc_info=exc)
            span.record_exception(exc)
    (res,) = _msearch([lexical_body])
    fused = rrf_fuse([res["hits"]["hits"]], RANK_WINDOW, RRF_K, RANK_WINDOW)
    return rerank(user, fused, 1, size), res.get("aggregations", {}), "bm25"


@router.get("/match")
def match(
    user_id: str = settings.demo_user,
    q: str = "",
    school: str = "",
    company: str = "",
    community: str = "",
    interest: str = "",
    country: str = "",
    city: str = "",
    kind: str = "",
    size: int = 20,
) -> dict:
    """People ranked for the user's current profile, each with up to three reasons, plus counts of others sharing
    the user's values. `mode` says how the ranking ran and `semantic` whether the profile vector took part.
    """
    filters = {"school": school, "company": company, "community": community, "interest": interest}
    filters |= {"country": country, "city": city}
    match_requests.add(1, {"kind": kind or "all", "has_query": bool(q.strip()), "filtered": any(filters.values())})
    user, vector = _load_user(user_id)
    activity.record("match", user_id, q.strip())  # only once the user is known to exist
    results, aggs, mode = rank_people(
        user_id,
        user,
        vector,
        q.strip(),
        kind or None,
        build_filters(filters),
        build_group_aggs(user),
        max(1, min(size, RANK_WINDOW)),
    )
    span = trace.get_current_span()
    span.set_attribute("confox.match.semantic", mode != "bm25")
    span.set_attribute("confox.match.mode", mode)
    for r in results:
        r.pop("affinity", None)
    return {"results": results, "groups": parse_groups(user, aggs), "semantic": mode != "bm25", "mode": mode}


@router.get("/{person_id}")
def profile(person_id: str) -> dict:
    try:
        doc = es.get(index=settings.idx_people, id=person_id, source_excludes=SOURCE_EXCLUDES)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"unknown person {person_id}") from exc
    return _person(doc)
