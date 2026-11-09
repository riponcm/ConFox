"""Session details: everything about one session for the drawer that opens when a title is clicked.

GET /api/sessions/{session_id}?user_id=emma

The session itself (full description, its vector read with `source_exclude_vectors=False`), the user's profile,
agenda and people are read first; then one `msearch` fetches the speakers, the speakers' other sessions, the kNN
neighbours of the session's own vector, later sessions in the same track, whether a transcript exists and who is
going. A failing part of the msearch is logged and recorded on the span and left empty, so the drawer still opens.
The shaping rules are pure functions, tested without Elasticsearch in tests/test_sessions.py.
"""

import logging
import math
import re

from elasticsearch import ApiError, NotFoundError
from fastapi import APIRouter, HTTPException, Query
from opentelemetry import trace

from .. import agenda_store as store
from ..config import settings
from ..es import es
from .schedule import (
    _all_agenda,
    _profile,
    _top_matches,
    blocking_items,
    friends,
    going_body,
    interest_matches,
    overlap_labels,
    parse_going,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])
tracer = trace.get_tracer("confox.sessions")
log = logging.getLogger(__name__)

SIMILAR = 5
TRACK_LATER = 5
OTHER_SESSIONS = 3  # per speaker
GOING_NAMES = 8
BIO_CHARS = 600
NOT_ADDABLE = {"break", "registration"}
# Cosine between the profile vector and the session vector (text-embedding-3-small). On the demo data Emma's
# scores run from 0.12 to 0.55, median 0.39, top quarter above 0.43: the buckets follow that spread.
SIMILARITY_BUCKETS = (
    (0.48, "very_close", "Very close to your profile"),
    (0.43, "close", "Close to your profile"),
    (0.38, "related", "Somewhat related to your profile"),
)
DISTANT = ("distant", "Not close to your profile")
LIST_FIELDS = ["title", "starts_at", "ends_at", "day", "kind", "is_food", "track", "level", "room", "speaker_ids"]
SPEAKER_FIELDS = ["name", "title", "company", "bio", "picture", "links", "session_ids"]
NOT_LISTED = [{"terms": {"kind": ["registration", "break"]}}, {"term": {"is_food": True}}]


# ---------- pure rules ----------


def cosine(a: list[float] | None, b: list[float] | None) -> float | None:
    """Cosine similarity of two vectors, or None when either is missing, empty or zero, or the sizes differ."""
    if not a or not b or len(a) != len(b):
        return None
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else None


def similarity_bucket(score: float | None) -> dict | None:
    """{"score", "bucket", "label"} for a profile-to-session cosine; None without vectors."""
    if score is None:
        return None
    bucket, label = next(((b, lbl) for floor, b, lbl in SIMILARITY_BUCKETS if score >= floor), DISTANT)
    return {"score": round(score, 3), "bucket": bucket, "label": label}


def title_has_words(title: str, phrase: str) -> bool:
    """Every word of the phrase is a whole word of the title, in any order: "AI inference" is in "Cloud Native AI
    + Inference Day" even though the phrase itself is not."""
    words = re.findall(r"[A-Za-z0-9]{2,}", phrase)
    return bool(words) and all(re.search(rf"\b{re.escape(w)}\b", title, re.I) for w in words)


def why_matches(session: dict, profile: dict, similarity: dict | None) -> list[dict]:
    """Why the session fits the user, as chips: profile interests found in the session (a phrase found only in the
    track counts as a track match), profile projects, then how close the vectors are when that is close or better.
    Each is {"kind": "interest" | "project" | "track" | "similar", "label", "where"?}."""
    interests = [i for i in profile.get("interests") or [] if i and i.strip()]
    projects = [p for p in profile.get("projects") or [] if p and p.strip() and p not in interests]
    out: list[dict] = []
    for value, where in interest_matches(session, interests):
        kind = "track" if where == "track" else "interest"
        label = f"Track: {session.get('track')}" if kind == "track" else f"Matches {value}"
        out.append({"kind": kind, "label": label, "value": value, "where": where})
    found = {w["value"] for w in out}
    title = session.get("title") or ""
    for value in interests:
        if value not in found and title_has_words(title, value):
            out.append({"kind": "interest", "label": f"Related to {value}", "value": value, "where": "title"})
    for value, where in interest_matches(session, projects):
        out.append({"kind": "project", "label": f"Uses {value}", "value": value, "where": where})
    if similarity and similarity["bucket"] in ("very_close", "close"):
        out.append({"kind": "similar", "label": similarity["label"]})
    # A track can match more than one interest phrase; show it once.
    unique: dict[str, dict] = {}
    for w in out:
        unique.setdefault(w["label"], w)
    return list(unique.values())


def list_item(hit: dict, agenda_ids: set[str]) -> dict:
    """A short session for the drawer's lists (similar, same track later, a speaker's other sessions)."""
    s = hit["_source"]
    item = {k: s.get(k) for k in LIST_FIELDS if k != "speaker_ids"} | {"id": hit["_id"]}
    item["on_agenda"] = hit["_id"] in agenda_ids
    return item


def pick_similar(knn_hits: list[dict], track_hits: list[dict], agenda_ids: set[str], limit: int = SIMILAR) -> dict:
    """The kNN neighbours when there are any (`basis: "semantic"`), else later sessions in the same track
    (`basis: "track"`), else nothing. kNN scores are kept so the list can say how close each one is."""
    if knn_hits:
        items = []
        for h in knn_hits[:limit]:
            item = list_item(h, agenda_ids)
            if h.get("_score") is not None:
                item["score"] = round(float(h["_score"]), 3)
            items.append(item)
        return {"basis": "semantic", "items": items}
    if track_hits:
        return {"basis": "track", "items": [list_item(h, agenda_ids) for h in track_hits[:limit]]}
    return {"basis": "none", "items": []}


def speakers_out(session: dict, people: list[dict], others: list[dict], agenda_ids: set[str]) -> list[dict]:
    """Speakers in the session's own order. `people` are confox-people hits, `others` session hits of the same
    speakers (this session already left out). A speaker without a profile keeps their published name."""
    by_id = {p["_id"]: p["_source"] for p in people}
    names = session.get("speaker_names") or []
    out = []
    for i, sid in enumerate(session.get("speaker_ids") or []):
        p = by_id.get(sid, {})
        bio = (p.get("bio") or "").strip()
        theirs = [h for h in others if sid in (h["_source"].get("speaker_ids") or [])]
        out.append(
            {
                "id": sid,
                "name": p.get("name") or (names[i] if i < len(names) else "Speaker"),
                "title": p.get("title") or "",
                "company": p.get("company") or "",
                "bio": bio if len(bio) <= BIO_CHARS else bio[: BIO_CHARS - 1].rstrip() + "…",
                "picture": p.get("picture"),
                "links": [
                    {"title": link.get("title") or "Link", "url": link["url"]}
                    for link in p.get("links") or []
                    if isinstance(link, dict) and str(link.get("url") or "").startswith(("https://", "http://"))
                ],
                "other_sessions": [list_item(h, agenda_ids) for h in theirs[:OTHER_SESSIONS]],
            }
        )
    return out


def agenda_session_ids(agenda: list[dict]) -> set[str]:
    """Sessions the user has confirmed on the agenda."""
    return {
        i["session_id"]
        for i in agenda
        if i.get("kind") == "session" and i.get("status") == "confirmed" and i.get("session_id")
    }


def similar_body(session_id: str, vector: list[float], k: int = SIMILAR) -> dict:
    """kNN on the session's own vector; itself, breaks, food and registration left out by pre-filter."""
    flt = {"bool": {"must_not": [{"ids": {"values": [session_id]}}, *NOT_LISTED]}}
    return {
        "knn": {"field": "embedding", "query_vector": vector, "k": k, "num_candidates": 100, "filter": flt},
        "size": k,
        "_source": LIST_FIELDS,
    }


def track_later_body(session: dict, limit: int = TRACK_LATER) -> dict | None:
    """Sessions in the same track that start at or after this one, earliest first. None without a track."""
    if not session.get("track"):
        return None
    return {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"track": session["track"]}},
                    {"range": {"starts_at": {"gte": session["starts_at"]}}},
                ],
                "must_not": [{"ids": {"values": [session["id"]]}}, *NOT_LISTED],
            }
        },
        "sort": [{"starts_at": "asc"}],
        "size": limit,
        "_source": LIST_FIELDS,
    }


def speakers_body(speaker_ids: list[str]) -> dict:
    return {"query": {"ids": {"values": speaker_ids}}, "size": len(speaker_ids), "_source": SPEAKER_FIELDS}


def others_body(session_id: str, speaker_ids: list[str]) -> dict:
    return {
        "query": {
            "bool": {
                "filter": [{"terms": {"speaker_ids": speaker_ids}}],
                "must_not": [{"ids": {"values": [session_id]}}],
            }
        },
        "sort": [{"starts_at": "asc"}],
        "size": 50,
        "_source": LIST_FIELDS,
    }


def transcript_body(session_id: str) -> dict:
    return {
        "query": {"bool": {"filter": [{"term": {"doc_type": "chunk"}}, {"term": {"session_id": session_id}}]}},
        "size": 0,
        "track_total_hits": True,
    }


def detail(
    session: dict,
    profile: dict,
    profile_vector: list[float] | None,
    session_vector: list[float] | None,
    agenda: list[dict],
    agenda_kinds: dict[str, str],
    parts: dict[str, dict | None],
    people: dict[str, str],
) -> dict:
    """The response from the session (with `id`) and the msearch parts (None where a part failed or was not
    asked). `agenda_kinds` maps agenda session ids to their kind, for leaving co-located days out of clashes."""
    hits = {name: (r or {}).get("hits", {}).get("hits", []) for name, r in parts.items()}
    on_ids = agenda_session_ids(agenda)
    blockers = blocking_items(agenda, agenda_kinds | {session["id"]: session.get("kind", "")})
    similarity = similarity_bucket(cosine(profile_vector, session_vector))
    going = parse_going((parts.get("going") or {}).get("aggregations", {}), people, GOING_NAMES).get(session["id"], {})
    transcript = parts.get("transcript") or {}
    chunks = transcript.get("hits", {}).get("total", {}).get("value", 0)
    track_later = [list_item(h, on_ids) for h in hits.get("track_later", [])]
    kind = session.get("kind") or ""
    return {
        "session": session,
        "speakers": speakers_out(session, hits.get("speakers", []), hits.get("others", []), on_ids),
        "on_agenda": session["id"] in on_ids,
        "can_add": kind not in NOT_ADDABLE and not session.get("is_food"),
        "clashes": overlap_labels(session, blockers),
        "going": going.get("going", 0),
        "going_names": going.get("going_names", []),
        "why": why_matches(session, profile, similarity),
        "similarity": similarity,
        "similar": pick_similar(hits.get("similar", []), hits.get("track_later", []), on_ids),
        "same_track_later": track_later,
        "catch_up": {"available": chunks > 0, "chunks": chunks},
        "slides_url": session.get("slides_url") or None,
    }


# ---------- Elasticsearch ----------


def _session(session_id: str) -> tuple[dict, list[float] | None]:
    try:
        doc = es.get(index=settings.idx_sessions, id=session_id, source_exclude_vectors=False)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"unknown session {session_id}") from exc
    source = dict(doc["_source"])
    vector = source.pop("embedding", None)
    return source | {"id": session_id}, vector if isinstance(vector, list) and vector else None


def _msearch(searches: dict[str, tuple[str, dict]]) -> dict[str, dict | None]:
    """Run named bodies as one msearch; a failed body comes back as None (logged and recorded on the span)."""
    names = list(searches)
    lines: list[dict] = []
    for name in names:
        index, body = searches[name]
        lines += [{"index": index, "ignore_unavailable": True}, body]
    span = trace.get_current_span()
    try:
        responses = es.msearch(searches=lines)["responses"]
    except ApiError as exc:
        log.warning("session detail: msearch failed: %s", exc)
        span.record_exception(exc)
        return dict.fromkeys(names)
    out: dict[str, dict | None] = {}
    for name, r in zip(names, responses, strict=True):
        if "error" in r:
            log.warning("session detail: %s unavailable: %s", name, r["error"])
            span.add_event("confox.session.part_failed", {"part": name, "error": str(r["error"])[:500]})
            out[name] = None
        else:
            out[name] = r
    return out


@router.get("/{session_id}")
def session_detail(session_id: str, user_id: str = Query(default_factory=lambda: settings.demo_user)) -> dict:
    span = trace.get_current_span()
    span.set_attribute("confox.session.id", session_id)
    with tracer.start_as_current_span("session.read"):
        session, vector = _session(session_id)
    with tracer.start_as_current_span("session.user"):
        profile, profile_vector = _profile(user_id)
        agenda = _all_agenda(user_id)
        people = friends(agenda, _top_matches(user_id, profile, profile_vector))
        kinds = store.session_kinds([i.get("session_id") or "" for i in agenda])

    speaker_ids = list(session.get("speaker_ids") or [])
    searches: dict[str, tuple[str, dict]] = {
        "transcript": (settings.idx_transcripts, transcript_body(session_id)),
        "going": (settings.idx_agenda, going_body([session_id], user_id, list(people))),
    }
    if speaker_ids:
        searches["speakers"] = (settings.idx_people, speakers_body(speaker_ids))
        searches["others"] = (settings.idx_sessions, others_body(session_id, speaker_ids))
    if vector:
        searches["similar"] = (settings.idx_sessions, similar_body(session_id, vector))
    later = track_later_body(session)
    if later:
        searches["track_later"] = (settings.idx_sessions, later)
    with tracer.start_as_current_span("session.related") as related:
        related.set_attribute("confox.session.parts", ",".join(searches))
        parts = _msearch(searches)

    out = detail(session, profile, profile_vector, vector, agenda, kinds, parts, people)
    span.set_attribute("confox.session.kind", session.get("kind") or "")
    span.set_attribute("confox.session.speakers", len(out["speakers"]))
    span.set_attribute("confox.session.similar", len(out["similar"]["items"]))
    span.set_attribute("confox.session.similar_basis", out["similar"]["basis"])
    span.set_attribute("confox.session.going", out["going"])
    span.set_attribute("confox.session.catch_up", out["catch_up"]["available"])
    return out
