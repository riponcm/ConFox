"""Schedule: one day of sessions with the user's agenda, marked "for you" where they fit the profile.

For you is decided by plain rules first (agenda, keynotes, food, interest phrases in the session text), plus a
kNN pick of the closest sessions when profile and session vectors exist. The rules are pure functions so they can
be tested without Elasticsearch.

The day view also carries, per session, how many other attendees saved it (`going`) and which of the user's
people did (`going_names`: confirmed meeting partners first, then the top Match results), plus the day's
summary, facet counts and the profile chips. That costs two more requests: the Match query (names) and one
agenda aggregation (terms on session_id with a terms on user_id limited to those people).
"""

import logging
import re

from elasticsearch import ApiError, NotFoundError
from fastapi import APIRouter, Query
from opentelemetry import trace

from ..clock import now
from ..config import settings
from ..es import es
from .people import build_match_query

router = APIRouter(prefix="/api/schedule", tags=["schedule"])
log = logging.getLogger(__name__)

DESCRIPTION_CHARS = 300
KNN_K = 12
MAX_REASONS = 2
DAY_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
NOT_REGISTRATION = {"bool": {"must_not": [{"term": {"kind": "registration"}}]}}
# Where an interest phrase appears says how strongly it fits; dict order is the ranking.
PLACE_FIT = {"title": 0.85, "projects": 0.8, "track": 0.65, "description": 0.5}
ANCHOR_FIT = {"keynote": 0.6, "food": 0.5}
SLOT_PICKS = 2
SECOND_PICK_FIT = 0.75
FRIENDS = 10  # top Match results counted as the user's people, on top of meeting partners
GOING_NAMES = 3
DAY_FACETS = ("kind", "track", "level", "venue")


# ---------- pure rules ----------


def _phrase(interest: str) -> re.Pattern[str]:
    return re.compile(rf"\b{re.escape(interest.strip())}\b", re.I)


def interest_matches(session: dict, interests: list[str]) -> list[tuple[str, str]]:
    """Interests found in the session as (interest, where), best place first. `where` is the strongest field the
    phrase appears in: title, projects, track, then description."""
    fields = {
        "title": session.get("title") or "",
        "projects": " ".join(session.get("projects") or []),
        "track": session.get("track") or "",
        "description": session.get("description") or "",
    }
    found = []
    for interest in interests:
        if not interest or not interest.strip():
            continue
        pattern = _phrase(interest)
        where = next((name for name, text in fields.items() if pattern.search(text)), None)
        if where:
            found.append((interest, where))
    return sorted(found, key=lambda m: list(PLACE_FIT).index(m[1]))


def _title_words(title: str, interests: list[str]) -> int:
    """How many distinct interest words (prefix match, so "GPU" finds "GPUs") the title contains. Breaks ties
    between sessions that only share a track."""
    words = {w.lower() for i in interests for w in re.findall(r"[A-Za-z]{3,}", i)}
    lowered = title.lower()
    return sum(1 for w in words if re.search(rf"\b{re.escape(w)}", lowered))


def for_you(
    session: dict,
    interests: list[str],
    on_agenda: bool = False,
    knn_score: float | None = None,
) -> tuple[bool, list[str], float]:
    """Return (for_you, why, fit) for one session. `knn_score` is set only for the day's top kNN neighbours."""
    reasons: list[str] = []
    fit = 0.0
    if on_agenda:
        reasons.append("on your agenda")
        fit = 1.0
    if session.get("kind") == "keynote":
        reasons.append("keynote")
        fit = max(fit, ANCHOR_FIT["keynote"])
    if session.get("is_food"):
        reasons.append("food and coffee")
        fit = max(fit, ANCHOR_FIT["food"])
    matches = interest_matches(session, interests)
    if matches:
        reasons.extend(f"matches {interest}" for interest, _ in matches)
        score = PLACE_FIT[matches[0][1]] + 0.05 * (len(matches) - 1)
        score += 0.02 * min(3, _title_words(session.get("title") or "", interests))
        fit = max(fit, min(score, 0.95))
    if knn_score is not None:
        reasons.append("close to your interests")
        fit = max(fit, min(max(knn_score, 0.0), 0.9))
    return bool(reasons), reasons[:MAX_REASONS], round(fit, 3)


def pick_per_slot(sessions: list[dict]) -> list[dict]:
    """Keep For you short: you can only sit in one room at a time. Agenda items, keynotes and food always stay;
    among the other picks that start together, keep the best one, plus a second only when it is a strong fit.
    The rest keep their reasons but drop out of For you (they still show in Everything)."""
    slots: dict[str, list[dict]] = {}
    for s in sessions:
        anchored = s.get("on_agenda") or s.get("kind") == "keynote" or s.get("is_food")
        if s.get("for_you") and not anchored:
            slots.setdefault(s["starts_at"], []).append(s)
    for picks in slots.values():
        picks.sort(key=lambda s: -s["fit"])
        for rank, s in enumerate(picks):
            keep = rank == 0 or (rank < SLOT_PICKS and s["fit"] >= SECOND_PICK_FIT)
            if not keep:
                s["for_you"] = False
    return sessions


def overlaps(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    """Times are ISO strings in one local time zone, so string comparison orders them correctly."""
    return a_start < b_end and b_start < a_end


def item_label(item: dict) -> str:
    if item.get("kind") == "meeting" and item.get("with_name"):
        return f"{item.get('title') or 'Meeting'} with {item['with_name']}"
    return item.get("title") or "Agenda item"


def blocking_items(agenda: list[dict], kind_by_session: dict[str, str]) -> list[dict]:
    """Confirmed agenda items that can clash. A full-day co-located event is something you drop in and out of;
    counting it would make every other session that day a clash, so it is left out."""
    return [
        item
        for item in agenda
        if item.get("status") == "confirmed" and kind_by_session.get(item.get("session_id") or "") != "colocated"
    ]


def clashes(session: dict, blockers: list[dict]) -> list[str]:
    """Labels of confirmed agenda items overlapping this session. Breaks and co-located days never clash: a
    meeting over coffee happens at the break, and a full-day event is not a single slot."""
    if session.get("kind") in ("break", "colocated"):
        return []
    return [
        item_label(item)
        for item in blockers
        if item.get("session_id") != session.get("id")
        and overlaps(session["starts_at"], session["ends_at"], item["starts_at"], item["ends_at"])
    ]


def annotate(
    sessions: list[dict],
    profile: dict,
    agenda: list[dict],
    knn_scores: dict[str, float] | None = None,
) -> list[dict]:
    """Add for_you, why, fit, on_agenda and clashes to each session (new dicts; the input is not changed)."""
    knn_scores = knn_scores or {}
    interests = list(profile.get("interests") or []) + list(profile.get("projects") or [])
    interests = list(dict.fromkeys(interests))
    on_agenda_ids = {i.get("session_id") for i in agenda if i.get("kind") == "session" and i.get("session_id")}
    blockers = blocking_items(agenda, {s["id"]: s.get("kind", "") for s in sessions})
    out = []
    for s in sessions:
        is_on = s["id"] in on_agenda_ids
        mine, why, fit = for_you(s, interests, is_on, knn_scores.get(s["id"]))
        out.append(s | {"for_you": mine, "why": why, "fit": fit, "on_agenda": is_on, "clashes": clashes(s, blockers)})
    return pick_per_slot(out)


def truncate(text: str, limit: int = DESCRIPTION_CHARS) -> str:
    text = text or ""
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


# ---------- day view extras: going, overlaps, summary, facets, chips (pure) ----------


def profile_chips(profile: dict) -> list[str]:
    """The profile's interests then projects, without repeats: the chips above the day and the phrases For you
    looks for."""
    values = list(profile.get("interests") or []) + list(profile.get("projects") or [])
    return list(dict.fromkeys(v.strip() for v in values if v and v.strip()))


def on_day(items: list[dict], day: str) -> list[dict]:
    """Agenda items that start on `day` (YYYY-MM-DD)."""
    return [i for i in items if (i.get("starts_at") or "")[:10] == day]


def friends(agenda: list[dict], matches: list[dict], limit: int = FRIENDS) -> dict[str, str]:
    """The user's people as {id: name}, in the order names are shown: confirmed meeting partners (any day), then
    the top `limit` Match results. `matches` are people with `id` and `name`."""
    out: dict[str, str] = {}
    for item in agenda:
        if item.get("kind") == "meeting" and item.get("status") == "confirmed" and item.get("with_id"):
            out.setdefault(item["with_id"], item.get("with_name") or item["with_id"])
    for person in matches[:limit]:
        if person.get("id"):
            out.setdefault(person["id"], person.get("name") or person["id"])
    return out


def going_body(session_ids: list[str], user_id: str, friend_ids: list[str]) -> dict:
    """One aggregation over confirmed saved sessions of everyone but the user: per session, how many people, and
    which of the user's people."""
    aggs: dict = {"people": {"cardinality": {"field": "user_id"}}}
    if friend_ids:
        aggs["friends"] = {
            "filter": {"terms": {"user_id": friend_ids}},
            "aggs": {"who": {"terms": {"field": "user_id", "size": len(friend_ids)}}},
        }
    return {
        "size": 0,
        "query": {
            "bool": {
                "filter": [
                    {"term": {"kind": "session"}},
                    {"term": {"status": "confirmed"}},
                    {"terms": {"session_id": session_ids}},
                ],
                "must_not": [{"term": {"user_id": user_id}}],
            }
        },
        "aggs": {"sessions": {"terms": {"field": "session_id", "size": max(1, len(session_ids))}, "aggs": aggs}},
    }


def parse_going(aggs: dict, people: dict[str, str], limit: int = GOING_NAMES) -> dict[str, dict]:
    """{session_id: {"going": n, "going_names": [...]}} from the aggregation; names in the order of `people`."""
    order = list(people)
    out = {}
    for bucket in aggs.get("sessions", {}).get("buckets", []):
        ids = {b["key"] for b in bucket.get("friends", {}).get("who", {}).get("buckets", [])}
        names = [people[p] for p in order if p in ids][:limit]
        count = int(bucket.get("people", {}).get("value", bucket["doc_count"]))
        out[bucket["key"]] = {"going": max(count, len(names)), "going_names": names}
    return out


def overlap_labels(session: dict, blockers: list[dict]) -> list[str]:
    """Like clashes(), but a co-located event shows what it overlaps too ("overlaps Coffee with Alice Moreno"):
    the day view says so even though nobody sits in a full-day event the whole time. Breaks still never do."""
    if session.get("kind") != "colocated":
        return clashes(session, blockers)
    return clashes(session | {"kind": "colocated-slot"}, blockers)


def day_extras(sessions: list[dict], agenda: list[dict], going: dict[str, dict]) -> list[dict]:
    """Annotated sessions plus `going`, `going_names`, and overlaps for co-located events (new dicts)."""
    blockers = blocking_items(agenda, {s["id"]: s.get("kind", "") for s in sessions})
    out = []
    for s in sessions:
        g = going.get(s["id"], {})
        extra = {"going": g.get("going", 0), "going_names": g.get("going_names", [])}
        if s.get("kind") == "colocated":
            extra["clashes"] = overlap_labels(s, blockers)
        out.append(s | extra)
    return out


def summary(sessions: list[dict]) -> dict:
    return {
        "for_you": sum(1 for s in sessions if s.get("for_you")),
        "total": len(sessions),
        "on_agenda": sum(1 for s in sessions if s.get("on_agenda")),
    }


def day_facets(sessions: list[dict]) -> dict[str, list[dict]]:
    """Counts per kind, track, level and venue over the day's sessions, most common first; empty values left out."""
    out = {}
    for name in DAY_FACETS:
        counts: dict[str, int] = {}
        for s in sessions:
            value = s.get(name)
            if value:
                counts[value] = counts.get(value, 0) + 1
        out[name] = [{"key": k, "count": n} for k, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    return out


# ---------- Elasticsearch ----------


def _day_sessions(day: str) -> list[dict]:
    r = es.search(
        index=settings.idx_sessions,
        query={"bool": {"filter": [{"term": {"day": day}}], **NOT_REGISTRATION["bool"]}},
        sort=[{"starts_at": "asc"}, {"ends_at": "asc"}],
        size=1000,
        source_excludes=["embedding"],
    )
    return [
        h["_source"] | {"id": h["_id"], "description": truncate(h["_source"].get("description"))}
        for h in r["hits"]["hits"]
    ]


def _profile(user_id: str) -> tuple[dict, list[float] | None]:
    """The profile and its vector, if the vector exists yet. Elasticsearch 9 leaves dense vectors out of _source
    unless asked."""
    try:
        doc = es.get(index=settings.idx_people, id=user_id, source_exclude_vectors=False)
    except NotFoundError:
        log.warning("schedule: no profile for user %s", user_id)
        return {}, None
    source = dict(doc["_source"])
    vector = source.pop("embedding", None)
    return source, vector if isinstance(vector, list) and vector else None


def _agenda(user_id: str, day: str) -> list[dict]:
    r = es.search(
        index=settings.idx_agenda,
        query={"bool": {"filter": [{"term": {"user_id": user_id}}]}},
        sort=[{"starts_at": "asc"}],
        size=500,
    )
    items = [h["_source"] | {"id": h["_id"]} for h in r["hits"]["hits"]]
    return [i for i in items if (i.get("starts_at") or "")[:10] == day]


def _all_agenda(user_id: str) -> list[dict]:
    """Every agenda item of the user (meeting partners on other days count as the user's people too)."""
    r = es.search(
        index=settings.idx_agenda,
        query={"bool": {"filter": [{"term": {"user_id": user_id}}]}},
        sort=[{"starts_at": "asc"}],
        size=500,
    )
    return [h["_source"] | {"id": h["_id"]} for h in r["hits"]["hits"]]


def _top_matches(user_id: str, profile: dict, vector: list[float] | None) -> list[dict]:
    """The top Match results (same query as /api/people/match), names only; lexical if vector scoring fails."""
    if not profile:
        return []

    def run(vec: list[float] | None) -> list[dict]:
        r = es.search(
            index=settings.idx_people,
            query=build_match_query(user_id, profile, vector=vec),
            size=FRIENDS,
            source_includes=["name"],
        )
        return [{"id": h["_id"], "name": h["_source"].get("name")} for h in r["hits"]["hits"]]

    try:
        return run(vector)
    except ApiError as exc:
        # The vector may be missing or mid-rebuild; rank without it, and without names only if that fails too.
        log.warning("schedule: match for going names failed (vector=%s): %s", bool(vector), exc)
        trace.get_current_span().record_exception(exc)
    if not vector:
        return []
    try:
        return run(None)
    except ApiError as exc:
        log.warning("schedule: lexical match for going names failed: %s", exc)
        trace.get_current_span().record_exception(exc)
        return []


def _going(session_ids: list[str], user_id: str, people: dict[str, str]) -> dict[str, dict]:
    """Going counts and names per session; empty (logged on the span) if the aggregation fails, so the day still
    loads."""
    if not session_ids:
        return {}
    try:
        r = es.search(index=settings.idx_agenda, **going_body(session_ids, user_id, list(people)))
    except ApiError as exc:
        log.warning("schedule: going counts unavailable: %s", exc)
        trace.get_current_span().record_exception(exc)
        return {}
    return parse_going(r.get("aggregations", {}), people)


def _knn(day: str, vector: list[float]) -> dict[str, float]:
    """Top sessions of the day by similarity to the profile vector. Empty if the sessions have no vectors yet."""
    try:
        r = es.search(
            index=settings.idx_sessions,
            knn={
                "field": "embedding",
                "query_vector": vector,
                "k": KNN_K,
                "num_candidates": 200,
                "filter": {"bool": {"filter": [{"term": {"day": day}}], **NOT_REGISTRATION["bool"]}},
            },
            size=KNN_K,
            source=False,
        )
    except Exception as exc:
        # Vectors may be missing or mid-rebuild; the schedule still works on the rules alone.
        log.warning("schedule: kNN unavailable, using rules only: %s", exc)
        trace.get_current_span().record_exception(exc)
        return {}
    return {h["_id"]: float(h["_score"]) for h in r["hits"]["hits"]}


@router.get("/day")
def day(
    day: str = Query(pattern=DAY_PATTERN),
    user_id: str = Query(default_factory=lambda: settings.demo_user),
) -> dict:
    sessions = _day_sessions(day)
    profile, vector = _profile(user_id)
    every_item = _all_agenda(user_id)
    agenda = on_day(every_item, day)
    knn_scores = _knn(day, vector) if vector else {}
    people = friends(every_item, _top_matches(user_id, profile, vector))
    going = _going([s["id"] for s in sessions], user_id, people)
    span = trace.get_current_span()
    span.set_attribute("confox.schedule.day", day)
    span.set_attribute("confox.schedule.semantic", bool(knn_scores))
    span.set_attribute("confox.schedule.friends", len(people))
    annotated = day_extras(annotate(sessions, profile, agenda, knn_scores), agenda, going)
    span.set_attribute("confox.schedule.for_you", sum(1 for s in annotated if s["for_you"]))
    span.set_attribute("confox.schedule.friends_going", sum(1 for s in annotated if s["going_names"]))
    meetings = [i for i in agenda if i.get("kind") == "meeting"]
    return {
        "day": day,
        "now": now().isoformat(),
        "sessions": annotated,
        "meetings": [i for i in meetings if i.get("status") == "confirmed"],
        "pending": [i for i in agenda if i.get("status") == "pending"],
        "semantic": bool(knn_scores),
        "summary": summary(annotated),
        "facets": day_facets(annotated),
        "interests": profile_chips(profile),
    }


@router.get("/days")
def days() -> dict:
    r = es.search(
        index=settings.idx_sessions,
        query=NOT_REGISTRATION,
        size=0,
        aggs={"days": {"terms": {"field": "day", "size": 31, "order": {"_key": "asc"}}}},
    )
    return {"days": [{"day": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["days"]["buckets"]]}
