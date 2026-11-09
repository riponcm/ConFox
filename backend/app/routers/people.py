"""People: profiles and Match.

Match ranks other people for the signed-in user by what they share: schools, current or past company,
communities, city and interests. Each shared value adds a fixed boost, so the ranking is explainable, and the
"why" reasons are computed in Python from the same overlap. When the user's profile has an embedding, cosine
similarity is added on top as a smaller weighted term (see `build_match_query`).
"""

import logging

from elasticsearch import ApiError, NotFoundError
from fastapi import APIRouter, HTTPException
from opentelemetry import metrics, trace

from .. import activity
from ..config import settings
from ..es import es

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/people", tags=["people"])
match_requests = metrics.get_meter("confox.people").create_counter(
    "confox.match.requests", unit="{request}", description="People Match requests"
)

# Fixed boosts per shared value. Schools weigh most: alumni ties are the demo's headline reason.
BOOST = {"schools": 6.0, "company": 3.0, "communities": 2.0, "city": 2.0, "interests": 1.5}
RELATED_BOOST = 0.5  # soft text match of the user's interests, so speakers (track names) still rank by topic
VECTOR_WEIGHT = 4.0  # max contribution of cosine similarity; below one shared school by design
MAX_REASONS = 3
TEXT_FIELDS = ["name^3", "title^2", "company^2", "interests_text^2", "bio"]
SOURCE_EXCLUDES = ["embedding"]

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


def _values(doc: dict, field: str) -> list[str]:
    v = doc.get(field)
    if v is None or v == "":
        return []
    return [x for x in v if x] if isinstance(v, list) else [v]


def companies(doc: dict) -> list[str]:
    """Current company first, then past companies, without duplicates."""
    return list(dict.fromkeys(_values(doc, "company") + _values(doc, "past_companies")))


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


def why(user: dict, person: dict) -> list[dict]:
    """Up to three reasons, most telling first.

    Order: schools, the first shared interest, company, community, city, further interests, related topics, then
    interests named in the bio.
    """
    interests = _shared(_values(user, "interests"), _values(person, "interests"))
    reasons = [
        {"label": f"{v} alumni", "field": "schools", "value": v}
        for v in _shared(_values(user, "schools"), _values(person, "schools"))
    ]
    reasons += [{"label": f"Both into {v}", "field": "interests", "value": v} for v in interests[:1]]
    for v in _shared(companies(user), companies(person)):
        verb = "Works at" if v == person.get("company") else "Worked at"
        reasons.append({"label": f"{verb} {v}", "field": "company", "value": v})
    reasons += [
        {"label": f"Both in {v}", "field": "communities", "value": v}
        for v in _shared(_values(user, "communities"), _values(person, "communities"))
    ]
    reasons += [
        {"label": f"Also in {v}", "field": "city", "value": v}
        for v in _shared(_values(user, "city"), _values(person, "city"))
    ]
    reasons += [{"label": f"Both into {v}", "field": "interests", "value": v} for v in interests[1:]]
    verb = "Speaks on" if person.get("kind") == "speaker" else "Into"
    reasons += [{"label": f"{verb} {v}", "field": "interests", "value": v} for v in related_topics(user, person)]
    bio = (person.get("bio") or "").lower()
    named = [u for u in _values(user, "interests") if u not in interests and u.lower() in bio]
    reasons += [{"label": f"Mentions {v}", "field": "q", "value": v} for v in named]  # field q: a keyword search
    return reasons[:MAX_REASONS]


def related_topics(user: dict, person: dict) -> list[str]:
    """The person's topics that contain, or are contained in, one of the user's interests, ignoring case.

    Speakers' interests are session tracks ("AI Inference + Agentic"), which rarely equal an attendee interest
    ("AI inference") exactly. The person's own value is returned, so it works as an exact filter.
    """
    mine = [u.lower() for u in _values(user, "interests")]
    exact = set(_values(user, "interests"))
    return [
        p
        for p in _values(person, "interests")
        if p not in exact and any(u in p.lower() or p.lower() in u for u in mine)
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


def build_match_query(
    user_id: str, user: dict, q: str = "", kind: str | None = None, vector: list | None = None
) -> dict:
    """The scoring query: fixed boosts per shared value, plus an optional keyword match and vector similarity.

    Every candidate matches (minimum_should_match 0), so people with nothing in common still appear, just lower.
    With a vector the bool query is wrapped in script_score adding VECTOR_WEIGHT * max(0, cosine). A weighted sum
    rather than RRF keeps the explainable boosts in charge: a shared school always outranks a close embedding,
    and aggregations and post_filter keep working on one plain query.
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
    interests = _values(user, "interests")
    for v in interests:
        should.append(_boost("interests", [v], BOOST["interests"]))
    if interests:
        should.append(
            {"multi_match": {"query": " ".join(interests), "fields": ["interests_text", "bio"], "boost": RELATED_BOOST}}
        )

    query: dict = {
        "bool": {
            "must_not": [{"ids": {"values": [user_id]}}],
            "should": should,
            "minimum_should_match": 0,
        }
    }
    if q:
        query["bool"]["must"] = [{"multi_match": {"query": q, "fields": TEXT_FIELDS, "fuzziness": "AUTO"}}]
    if kind:
        query["bool"]["filter"] = build_filters({"kind": kind})
    if vector:
        query = {
            "script_score": {
                "query": query,
                "script": {
                    "source": "doc['embedding'].size() == 0 ? _score"
                    " : _score + params.w * Math.max(0, cosineSimilarity(params.v, 'embedding'))",
                    "params": {"v": vector, "w": VECTOR_WEIGHT},
                },
            }
        }
    return query


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
    """The user's profile and, if one exists, their embedding (Elasticsearch 9 leaves vectors out of _source)."""
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
    """People ranked for the user, each with up to three reasons, plus counts of others sharing the user's values.

    `semantic` says whether embedding similarity took part in the ranking.
    Filters other than kind go in post_filter, so group counts stay stable while the user toggles chips.
    """
    filters = {"school": school, "company": company, "community": community, "interest": interest}
    filters |= {"country": country, "city": city}
    match_requests.add(1, {"kind": kind or "all", "has_query": bool(q.strip()), "filtered": any(filters.values())})
    user, vector = _load_user(user_id)
    activity.record("match", user_id, q.strip())  # only once the user is known to exist
    post = build_filters(filters)
    body = {
        "size": max(1, min(size, 100)),
        "source_excludes": SOURCE_EXCLUDES,
        "aggs": build_group_aggs(user),
    }
    if post:
        body["post_filter"] = {"bool": {"filter": post}}

    def run(vec: list | None) -> dict:
        query = build_match_query(user_id, user, q.strip(), kind or None, vec)
        return es.search(index=settings.idx_people, query=query, **body)

    try:
        res = run(vector)
    except ApiError as exc:
        if not vector:
            raise
        # The vector field may be missing or being rebuilt; rank without it rather than fail the page.
        log.warning("vector scoring failed, falling back to lexical: %s", exc, exc_info=exc)
        trace.get_current_span().record_exception(exc)
        vector = None
        res = run(None)
    trace.get_current_span().set_attribute("confox.match.semantic", bool(vector))

    results = []
    for hit in res["hits"]["hits"]:
        person = _person(hit)
        results.append({**person, "score": round(float(hit["_score"] or 0), 3), "why": why(user, person)})
    groups = parse_groups(user, res.get("aggregations", {}))
    return {"results": results, "groups": groups, "semantic": bool(vector)}


@router.get("/{person_id}")
def profile(person_id: str) -> dict:
    try:
        doc = es.get(index=settings.idx_people, id=person_id, source_excludes=SOURCE_EXCLUDES)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"unknown person {person_id}") from exc
    return _person(doc)
