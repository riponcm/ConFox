"""Ask Confox: a question answered by Claude from retrieved sessions, people and sample transcripts.

POST /api/ask streams Server-Sent Events: `sources`, then `delta` text chunks, then `done` with tokens and cost.
"""

import logging
import re
from datetime import date, datetime, timedelta
from typing import Literal

from elasticsearch import ApiError, NotFoundError
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from opentelemetry import trace
from pydantic import BaseModel, Field, field_validator

from .. import activity, clock, embeddings, llm
from ..config import settings
from ..es import es
from . import people, search

router = APIRouter(prefix="/api/ask", tags=["ask"])
log = logging.getLogger(__name__)
tracer = trace.get_tracer("confox.ask")

SESSION_HITS = 8
PEOPLE_HITS = 5
TRANSCRIPT_HITS = 4
KNN_K = 20
RANK_WINDOW = 30
PEOPLE_KINDS = ["speaker", "attendee"]
NOT_SESSIONS = ["break", "registration"]


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class Conversation(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=20)

    @field_validator("messages")
    @classmethod
    def starts_and_ends_with_user(cls, v: list[Message]) -> list[Message]:
        if v[0].role != "user" or v[-1].role != "user":
            raise ValueError("the conversation must start and end with a user message")
        return v


class AskBody(Conversation):
    user_id: str = settings.demo_user


def spoken_now(now: datetime) -> str:
    return f"{now:%A} {now.day} {now:%B}, {now:%H:%M}"


def when(starts_at: str | None, ends_at: str | None = None) -> str:
    if not starts_at:
        return "time not set"
    s = datetime.fromisoformat(starts_at)
    out = f"{s:%a} {s.day} {s:%b} {s:%H:%M}"
    if ends_at:
        out += f"-{datetime.fromisoformat(ends_at):%H:%M}"
    return out


def profile(user_id: str) -> dict:
    try:
        return es.get(index=settings.idx_people, id=user_id, source_includes=["name", "title", "interests", "schools"])[
            "_source"
        ]
    except NotFoundError:
        return {}


WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def asked_day(question: str, today: date) -> date | None:
    """The day a question is about, when it names one ("today", "tomorrow", "on Wednesday")."""
    q = question.lower()
    if re.search(r"\b(today|tonight|this (morning|afternoon|evening)|right now|now)\b", q):
        return today
    if re.search(r"\btomorrow\b", q):
        return today + timedelta(days=1)
    for i, name in enumerate(WEEKDAYS):
        if re.search(rf"\b{name}\b", q):
            # The nearest such weekday, past or future: on Wednesday, "Tuesday" means yesterday, not next week.
            delta = i - today.weekday()
            if delta > 3:
                delta -= 7
            elif delta < -3:
                delta += 7
            return today + timedelta(days=delta)
    return None


def day_scope(day: date | None, today: date) -> tuple[list[dict], list[dict]]:
    """Filters and optional boosts for sessions. A named day is a filter; otherwise today gets a small nudge."""
    flt: list[dict] = [{"bool": {"must_not": {"terms": {"kind": NOT_SESSIONS}}}}]
    if day:
        return flt + [{"term": {"day": day.isoformat()}}], []
    return flt, [{"term": {"day": {"value": today.isoformat(), "boost": 1.5}}}]


def sessions_lexical(question: str, flt: list[dict], should: list[dict]) -> dict:
    query: dict = {
        "must": {"multi_match": {"query": question, "fields": search.TEXT_FIELDS}},
        "filter": flt,
    }
    if should:
        query["should"] = should
    return {"bool": query}


def people_scope(user_id: str) -> list[dict]:
    """Speakers and sample attendees, never the person asking."""
    return [{"terms": {"kind": PEOPLE_KINDS}}, {"bool": {"must_not": {"ids": {"values": [user_id]}}}}]


def people_lexical(question: str, flt: list[dict]) -> dict:
    return {"bool": {"must": {"multi_match": {"query": question, "fields": people.TEXT_FIELDS}}, "filter": flt}}


def plain_body(query: dict, size: int) -> dict:
    return {"size": size, "query": query, "_source": {"excludes": ["embedding"]}}


def hybrid_body(lexical: dict, vector: list[float], flt: list[dict], size: int) -> dict:
    """BM25 and kNN fused by the native rrf retriever; the same filters go into both sides."""
    return {
        "size": size,
        "_source": {"excludes": ["embedding"]},
        "retriever": {
            "rrf": {
                "retrievers": [
                    {"standard": {"query": lexical}},
                    {"knn": search.knn(vector, KNN_K, flt)},
                ],
                "rank_window_size": RANK_WINDOW,
                "rank_constant": search.RRF_K,
            }
        },
    }


def knn_only_body(vector: list[float], flt: list[dict]) -> dict:
    return {"size": KNN_K, "knn": search.knn(vector, KNN_K, flt), "_source": {"excludes": ["embedding"]}}


def transcripts_body(question: str) -> dict:
    return {
        "size": TRANSCRIPT_HITS,
        "query": {"bool": {"must": {"match": {"text": question}}, "filter": {"term": {"doc_type": "chunk"}}}},
    }


Mode = Literal["hybrid", "hybrid-client", "bm25"]


def plan(
    question: str, user_id: str, today: date, vector: list[float] | None, mode: Mode, with_transcripts: bool
) -> list[tuple[str, dict]]:
    """The (index, body) pairs of the one msearch. Order matters: `collect` reads the answers back in this order.

    native: sessions, people. client: sessions BM25, sessions kNN, people BM25, people kNN (fused in Python).
    bm25: sessions, people. Transcript chunks, when that index exists, always come last.
    """
    s_flt, s_should = day_scope(asked_day(question, today), today)
    p_flt = people_scope(user_id)
    s_lex = sessions_lexical(question, s_flt, s_should)
    p_lex = people_lexical(question, p_flt)
    if vector is not None and mode == "hybrid":
        out = [
            (settings.idx_sessions, hybrid_body(s_lex, vector, s_flt, SESSION_HITS)),
            (settings.idx_people, hybrid_body(p_lex, vector, p_flt, PEOPLE_HITS)),
        ]
    elif vector is not None:
        out = [
            (settings.idx_sessions, plain_body(s_lex, RANK_WINDOW)),
            (settings.idx_sessions, knn_only_body(vector, s_flt)),
            (settings.idx_people, plain_body(p_lex, RANK_WINDOW)),
            (settings.idx_people, knn_only_body(vector, p_flt)),
        ]
    else:
        out = [
            (settings.idx_sessions, plain_body(s_lex, SESSION_HITS)),
            (settings.idx_people, plain_body(p_lex, PEOPLE_HITS)),
        ]
    if with_transcripts:
        out.append((settings.idx_transcripts, transcripts_body(question)))
    return out


def _hits(response: dict) -> list[dict]:
    return response["hits"]["hits"]


def _doc(hit: dict) -> dict:
    return {"id": hit["_id"], **hit["_source"]}


def collect(responses: list[dict], mode: Mode, vector_used: bool, with_transcripts: bool) -> tuple[list, list, list]:
    """Sessions, people and transcript chunks from the msearch responses laid out by `plan`."""
    chunks = [h["_source"] for h in _hits(responses[-1])] if with_transcripts else []
    if vector_used and mode == "hybrid-client":
        sessions = search.rrf_fuse([_hits(responses[0]), _hits(responses[1])], SESSION_HITS)
        found = search.rrf_fuse([_hits(responses[2]), _hits(responses[3])], PEOPLE_HITS)
    else:
        sessions, found = _hits(responses[0]), _hits(responses[1])
    return [_doc(h) for h in sessions], [_doc(h) for h in found], chunks


def run_retrieval(
    question: str, user_id: str, today: date, vector: list[float] | None, with_transcripts: bool
) -> tuple[Mode, list[dict], list[dict], list[dict]]:
    """Hybrid (native rrf), else client-side rrf when the cluster has no licence for it, else BM25 only."""
    if vector is not None and search.native_rrf_ok():
        try:
            reqs = plan(question, user_id, today, vector, "hybrid", with_transcripts)
            out = collect(search.msearch(reqs), "hybrid", True, with_transcripts)
            search.remember_native_rrf(True)
            return ("hybrid", *out)
        except (ApiError, search.SearchFailed) as exc:
            if not search.native_failed(exc):
                raise
            search.remember_native_rrf(False)
            log.warning("native rrf retriever not licensed on this cluster; using client-side RRF: %s", exc)
            span = trace.get_current_span()
            span.record_exception(exc)
            span.add_event("confox.search.rrf_fallback", {"reason": str(exc)[:500]})
    mode: Mode = "hybrid-client" if vector is not None else "bm25"
    reqs = plan(question, user_id, today, vector, mode, with_transcripts)
    return (mode, *collect(search.msearch(reqs), mode, vector is not None, with_transcripts))


def query_vector(question: str) -> list[float] | None:
    """The question embedded once, or None (no key, or the call failed: keyword search only)."""
    if not embeddings.enabled():
        return None
    try:
        return embeddings.embed([question])[0]
    except Exception as exc:
        log.warning("question embedding failed, using keyword search: %s", exc, exc_info=exc)
        trace.get_current_span().record_exception(exc)
        return None


def session_context(n: int, s: dict) -> str:
    details = [
        when(s.get("starts_at"), s.get("ends_at")),
        s.get("room") or "room not set",
        s.get("kind") or "",
        "Speakers: " + ", ".join(s.get("speaker_names") or []) if s.get("speaker_names") else "",
        f"Track: {s['track']}" if s.get("track") else "",
        "Projects: " + ", ".join(s["projects"]) if s.get("projects") else "",
    ]
    desc = (s.get("description") or "").replace("\n", " ")[:600]
    return f"[{n}] {s['title']} | " + " | ".join(d for d in details if d) + (f"\n{desc}" if desc else "")


def person_context(n: int, p: dict) -> str:
    """ "[7] Person: Alice Moreno, ML Engineer at Redwood Labs; interests: a, b; sample attendee"."""
    role = ", ".join(x for x in [p.get("title")] if x)
    if p.get("company"):
        role = f"{role} at {p['company']}" if role else p["company"]
    parts = [f"[{n}] Person: {p['name']}" + (f", {role}" if role else "")]
    if p.get("interests"):
        parts.append("interests: " + ", ".join(p["interests"][:8]))
    parts.append("sample attendee (generated, not a real person)" if p.get("sample") else "speaker")
    line = "; ".join(parts)
    bio = (p.get("bio") or "").replace("\n", " ")[:300]
    return line + (f"\n{bio}" if bio else "")


def build_sources(
    sessions: list[dict], people_found: list[dict], chunks: list[dict], titles: dict[str, str]
) -> tuple[list[dict], list[str]]:
    """Numbered sources (sessions, then people, then transcript chunks): browser entries and Claude's context lines."""
    sources: list[dict] = []
    context: list[str] = []
    for s in sessions:
        n = len(sources) + 1
        sources.append(
            {"n": n, "kind": "session", "id": s["id"], "title": s["title"]}
            | {"starts_at": s.get("starts_at"), "room": s.get("room"), "session_kind": s.get("kind")}
        )
        context.append(session_context(n, s))
    for p in people_found:
        n = len(sources) + 1
        sources.append(
            {
                "n": n,
                "kind": "person",
                "id": p["id"],
                "name": p["name"],
                "title": p.get("title"),
                "company": p.get("company"),
            }
            | {"sample": bool(p.get("sample")), "starts_at": None, "room": None}
        )
        context.append(person_context(n, p))
    for c in chunks:
        n = len(sources) + 1
        title = titles.get(c["session_id"], "a keynote")
        sources.append(
            {"n": n, "kind": "transcript", "id": c["session_id"], "title": f"Sample transcript: {title}"}
            | {"starts_at": None, "room": None, "chunk": c["chunk"]}
        )
        context.append(f"[{n}] Sample transcript (generated) of '{title}', part {c['chunk']}:\n{c['text']}")
    return sources, context


def retrieve(question: str, user_id: str) -> tuple[list[dict], list[str], dict]:
    """Sources for the answer: numbered entries for the browser and the matching context lines for Claude."""
    with tracer.start_as_current_span("retrieve") as span:
        vector = query_vector(question)
        with_transcripts = bool(es.indices.exists(index=settings.idx_transcripts))
        mode, sessions, found, chunks = run_retrieval(question, user_id, clock.now().date(), vector, with_transcripts)
        titles = {}
        if chunks:
            ids = list({c["session_id"] for c in chunks})
            docs = es.mget(index=settings.idx_sessions, ids=ids, source_includes=["title"])["docs"]
            titles = {d["_id"]: d["_source"]["title"] for d in docs if d.get("found")}
        user = profile(user_id)
        span.set_attribute("confox.retrieve.mode", mode)
        span.set_attribute("confox.retrieve.sessions", len(sessions))
        span.set_attribute("confox.retrieve.people", len(found))
        span.set_attribute("confox.retrieve.transcript_chunks", len(chunks))
    sources, context = build_sources(sessions, found, chunks, titles)
    return sources, context, user


def system_prompt(user: dict) -> str:
    who = [user.get("name") or "the attendee"]
    if user.get("title"):
        who.append(user["title"])
    if user.get("interests"):
        who.append("interests: " + ", ".join(user["interests"]))
    if user.get("schools"):
        who.append("school: " + ", ".join(user["schools"]))
    return (
        "You are Confox, a guide for KubeCon + CloudNativeCon North America 2026 in Salt Lake City.\n"
        f"It is {spoken_now(clock.now())} in Salt Lake City.\n"
        f"You are helping {'; '.join(who)}.\n"
        "Answer only from the numbered sources in the latest message. Cite them inline like [1] or [2][4]. "
        "Be concise: a short paragraph or a short list. Give day, time and room for sessions you suggest, and "
        "prefer ones that have not started yet. Sources marked 'Sample transcript (generated)' are fictional "
        "stand-ins, not the speaker's actual words; say so if you use one.\n"
        "Sources starting 'Person:' are people. You may recommend people to meet when it helps, say why they fit "
        "(shared interests, their talks, their work) and cite them like any source. People marked 'sample attendee' "
        "are generated demo profiles: always call them a sample attendee when you mention one. Never invent contact "
        "details, emails, handles or availability; offer only what the source states.\n"
        "If the sources do not answer the question, say that plainly instead "
        "of guessing. Plain text only, no headings."
    )


@router.post("")
def ask(body: AskBody) -> StreamingResponse:
    question = body.messages[-1].content
    activity.record("question", body.user_id, "ask")
    sources, context, user = retrieve(question, body.user_id)
    history = [m.model_dump() for m in body.messages[:-1]]
    latest = "Sources:\n" + ("\n\n".join(context) or "(none found)") + f"\n\nQuestion: {question}"
    messages = history + [{"role": "user", "content": latest}]
    return StreamingResponse(
        llm.sse_answer(sources, system_prompt(user), messages, feature="ask"),
        media_type="text/event-stream",
        headers=llm.SSE_HEADERS,
    )
