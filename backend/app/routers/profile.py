"""Profile: read and edit the signed-in user's profile, the input to People Match, For you and My brief.

A save writes the whole document with refresh, so the next Match or Schedule request ranks against it. The
embedding is recomputed from the same text recipe as the loader (`embeddings.person_text`), and only when that
text changed: editing schools or links costs no model call. Without an OpenAI key the profile is saved without a
vector and the response says so; matching then runs on keywords and shared background only.
"""

import logging
from typing import Annotated, Literal
from urllib.parse import urlparse

from elasticsearch import ApiError, NotFoundError
from fastapi import APIRouter, HTTPException
from fastapi.exceptions import RequestValidationError
from opentelemetry import metrics, trace
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from .. import embeddings
from ..clock import now
from ..config import settings
from ..es import es
from ..indices import PROFILE_FIELDS
from .people import topics

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/profile", tags=["profile"])
tracer = trace.get_tracer("confox.profile")
updates = metrics.get_meter("confox.profile").create_counter(
    "confox.profile.updates", unit="{update}", description="Profile saves"
)

FIRST_SCHOOL = "University of Utah"  # demo data lists it first wherever universities are ranked by default
HIDDEN_TRACKS = {"Registration", "Breaks"}
OPTION_SIZE = 40

# ---------- validation ----------


def _dedupe(values: list[str]) -> list[str]:
    """Drop repeats, ignoring case; the first spelling wins."""
    seen: set[str] = set()
    out = []
    for v in values:
        if v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)
    return out


def _url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or "." not in parsed.netloc:
        raise ValueError("must be a full http or https address, like https://github.com/emma")
    return value


Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)]
Item = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Phrase = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Url = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300), AfterValidator(_url)]


def _items(max_items: int, kind=Item):
    return Annotated[list[kind], Field(max_length=max_items), AfterValidator(_dedupe)]


class ProfileIn(BaseModel):
    """Everything the profile editor can change. Unknown fields are refused."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    title: Text = ""
    company: Text = ""
    city: Text = ""
    country: Text = ""
    bio: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] = ""
    interests: _items(12, Phrase) = []
    projects: _items(20, Phrase) = []
    tracks: _items(12) = []
    schools: _items(8) = []
    past_companies: _items(10) = []
    communities: _items(10) = []
    looking_for: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ""
    links: _items(3, Url) = []
    visibility: Literal["public", "private"] = "public"


EDITABLE = list(ProfileIn.model_fields)
LIST_FIELDS = {name for name, f in ProfileIn.model_fields.items() if f.default == []}

# ---------- pure helpers ----------


def editable(doc: dict) -> dict:
    """The editable fields of a stored profile, with empty defaults for fields it does not have yet."""
    out = {}
    for name in EDITABLE:
        default = [] if name in LIST_FIELDS else ("public" if name == "visibility" else "")
        value = doc.get(name)
        out[name] = default if value is None else value
    return out


def build_doc(existing: dict, update: ProfileIn, at: str) -> dict:
    """The stored document after a save: fields the editor does not own (kind, sample, picture, session ids) are
    kept, `interests_text` is rebuilt from every topic so BM25 and the embedding see them, the vector is left out."""
    doc = {k: v for k, v in existing.items() if k != "embedding"} | update.model_dump()
    doc["interests_text"] = ", ".join(topics(doc))
    doc["updated_at"] = at
    return doc


def changed_fields(old: dict, new: dict) -> list[str]:
    """Editable fields whose value differs, in form order. Missing, empty and default values count as equal."""
    before, after = editable(old), editable(new)
    return [name for name in EDITABLE if before[name] != after[name]]


def embedding_plan(old: dict, new: dict, has_vector: bool, enabled: bool) -> str:
    """`unchanged` (same text, keep the vector), `skipped` (no key: save without one) or `updated` (embed)."""
    if has_vector and embeddings.person_text(old) == embeddings.person_text(new):
        return "unchanged"
    return "updated" if enabled else "skipped"


def unknown_tracks(chosen: list[str], known: list[str]) -> list[str]:
    allowed = set(known)
    return [t for t in chosen if t not in allowed]


def _keys(agg: dict) -> list[str]:
    return [b["key"] for b in agg.get("buckets", [])]


def utah_first(schools: list[str]) -> list[str]:
    return sorted(schools, key=lambda s: s != FIRST_SCHOOL)  # stable: otherwise by count


def merge_counts(*aggs: dict) -> list[str]:
    """Bucket keys from several terms aggregations, by total count."""
    counts: dict[str, int] = {}
    for agg in aggs:
        for b in agg.get("buckets", []):
            counts[b["key"]] = counts.get(b["key"], 0) + b["doc_count"]
    return sorted(counts, key=lambda k: -counts[k])


def parse_options(people_aggs: dict, session_aggs: dict) -> dict[str, list[str]]:
    return {
        "interests": _keys(people_aggs["attendees"]["interests"]),
        "projects": _keys(session_aggs["projects"]),
        "tracks": [t for t in _keys(session_aggs["tracks"]) if t not in HIDDEN_TRACKS],
        "schools": utah_first(_keys(people_aggs["schools"])),
        "companies": merge_counts(people_aggs["company"], people_aggs["past_companies"])[:OPTION_SIZE],
        "communities": _keys(people_aggs["communities"]),
        "cities": _keys(people_aggs["city"]),
        "countries": _keys(people_aggs["country"]),
    }


def _terms(field: str, size: int = OPTION_SIZE) -> dict:
    return {"terms": {"field": field, "size": size}}


OPTION_AGGS = {
    "people": {
        "attendees": {"filter": {"term": {"kind": "attendee"}}, "aggs": {"interests": _terms("interests", 60)}},
        "schools": _terms("schools"),
        "company": _terms("company"),
        "past_companies": _terms("past_companies"),
        "communities": _terms("communities"),
        "city": _terms("city"),
        "country": _terms("country"),
    },
    "sessions": {"tracks": _terms("track", 60), "projects": _terms("projects", 80)},
}

# ---------- Elasticsearch ----------


def _known_tracks() -> list[str]:
    r = es.search(index=settings.idx_sessions, size=0, aggs={"tracks": OPTION_AGGS["sessions"]["tracks"]})
    return [t for t in _keys(r["aggregations"]["tracks"]) if t not in HIDDEN_TRACKS]


def _stored(user_id: str) -> tuple[dict, list | None]:
    try:
        doc = es.get(index=settings.idx_people, id=user_id, source_exclude_vectors=False)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"unknown user {user_id}") from exc
    src = dict(doc["_source"])
    vector = src.pop("embedding", None)
    return src, vector if isinstance(vector, list) and vector else None


def _ensure_mapping() -> None:
    """Add the profile-only fields to an index loaded before they existed (additive; a no-op when present)."""
    try:
        es.indices.put_mapping(index=settings.idx_people, properties=PROFILE_FIELDS)
    except ApiError as exc:  # the save still works with dynamic mapping; say so rather than fail it
        log.warning("profile: could not add profile fields to the mapping: %s", exc)
        trace.get_current_span().record_exception(exc)


def _response(user_id: str, doc: dict, has_vector: bool) -> dict:
    meta = {k: doc.get(k) for k in ("kind", "sample", "updated_at")}
    return {"id": user_id, **editable(doc), **meta, "has_embedding": has_vector}


@router.get("/options")
def options() -> dict[str, list[str]]:
    """Suggestions for the editor's chip inputs, from aggregations over people and sessions, most common first."""
    searches = [
        {"index": settings.idx_people},
        {"size": 0, "aggs": OPTION_AGGS["people"]},
        {"index": settings.idx_sessions},
        {"size": 0, "aggs": OPTION_AGGS["sessions"]},
    ]
    people, sessions = es.msearch(searches=searches)["responses"]
    for r in (people, sessions):
        if "error" in r:
            raise HTTPException(status_code=502, detail="could not load suggestions")
    return parse_options(people["aggregations"], sessions["aggregations"])


@router.get("/{user_id}")
def get_profile(user_id: str) -> dict:
    doc, vector = _stored(user_id)
    return _response(user_id, doc, vector is not None)


@router.put("/{user_id}")
def save_profile(user_id: str, update: ProfileIn) -> dict:
    """Validate, rebuild interests_text and the embedding, write with refresh, return the profile and what changed.

    Until real sign-in exists, the only person who can save is the signed-in demo user.
    """
    if user_id != settings.demo_user:
        raise HTTPException(status_code=403, detail="you can only edit your own profile")
    with tracer.start_as_current_span("profile.save") as span:
        span.set_attribute("confox.profile.user", user_id)
        if bad := unknown_tracks(update.tracks, _known_tracks()):
            raise RequestValidationError(
                [{"type": "value_error", "loc": ("body", "tracks"), "msg": f"unknown track: {', '.join(bad)}"}]
            )
        old, vector = _stored(user_id)
        doc = build_doc(old, update, now().isoformat(timespec="seconds"))
        changed = changed_fields(old, doc)
        plan = embedding_plan(old, doc, vector is not None, embeddings.enabled())
        note = ""
        if plan == "unchanged":
            doc["embedding"] = vector
        elif plan == "updated":
            try:
                doc["embedding"] = embeddings.embed([embeddings.person_text(doc)])[0]
            except Exception as exc:
                # Save the edit anyway; without a vector Match and For you run on keywords and shared background.
                log.warning("profile: embedding failed, saving without a vector: %s", exc, exc_info=exc)
                span.record_exception(exc)
                plan = "failed"
                note = "Saved, but the embedding could not be computed; matching uses keywords only until next save."
        else:
            note = "Saved without an embedding (no OPENAI_API_KEY); matching uses keywords and shared background only."

        _ensure_mapping()
        es.index(index=settings.idx_people, id=user_id, document=doc, refresh="wait_for")
        span.set_attribute("confox.profile.changed", ",".join(changed))
        span.set_attribute("confox.profile.embedding", plan)
        updates.add(1, {"embedding": plan, "changed": bool(changed)})
        log.info("profile %s saved: changed=%s embedding=%s", user_id, changed, plan)
        has_vector = "embedding" in doc
        return {"profile": _response(user_id, doc, has_vector), "changed": changed, "embedding": plan, "note": note}
