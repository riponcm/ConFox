"""Catch up on a missed keynote: sample transcript, a cached Claude summary, and questions grounded in that talk.

GET  /api/catchup                      talks that have a transcript
GET  /api/catchup/{session_id}         transcript chunks plus {tldr, takeaways}; summary generated once, then cached
POST /api/catchup/{session_id}/ask     Server-Sent Events like /api/ask, citing transcript parts
"""

import json
import logging

from elasticsearch import NotFoundError
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from opentelemetry import trace

from .. import clock, llm
from ..config import settings
from ..es import es
from .ask import Conversation, when

router = APIRouter(prefix="/api/catchup", tags=["catchup"])
tracer = trace.get_tracer("confox.catchup")
log = logging.getLogger(__name__)

SESSION_FIELDS = ["title", "starts_at", "ends_at", "room", "speaker_names", "description", "kind"]

SUMMARY_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "tldr": {"type": "string"},
            "takeaways": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["tldr", "takeaways"],
        "additionalProperties": False,
    },
}

SUMMARY_SYSTEM = (
    "You summarise a conference talk for someone who missed it, using only the transcript you are given. "
    "Return a TL;DR of two plain sentences and exactly three takeaways, each one short sentence a practitioner "
    "can act on or remember. Plain language, no markdown."
)


def _session(session_id: str) -> dict:
    try:
        s = es.get(index=settings.idx_sessions, id=session_id, source_includes=SESSION_FIELDS)["_source"]
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="unknown session") from exc
    return {
        "id": session_id,
        "title": s["title"],
        "starts_at": s.get("starts_at"),
        "ends_at": s.get("ends_at"),
        "room": s.get("room"),
        "speakers": s.get("speaker_names") or [],
        "kind": s.get("kind"),
        "sample": True,
    }


def _chunks(session_id: str) -> list[dict]:
    if not es.indices.exists(index=settings.idx_transcripts):
        return []
    r = es.search(
        index=settings.idx_transcripts,
        size=100,
        query={"bool": {"filter": [{"term": {"doc_type": "chunk"}}, {"term": {"session_id": session_id}}]}},
        sort=[{"chunk": "asc"}],
    )
    return [{"n": h["_source"]["chunk"], "text": h["_source"]["text"]} for h in r["hits"]["hits"]]


def _transcript_or_404(session_id: str) -> list[dict]:
    chunks = _chunks(session_id)
    if not chunks:
        raise HTTPException(status_code=404, detail="no transcript for this session")
    return chunks


@router.get("")
def talks() -> list[dict]:
    if not es.indices.exists(index=settings.idx_transcripts):
        return []
    r = es.search(
        index=settings.idx_transcripts,
        size=0,
        query={"term": {"doc_type": "chunk"}},
        aggs={"talks": {"terms": {"field": "session_id", "size": 50}}},
    )
    ids = [b["key"] for b in r["aggregations"]["talks"]["buckets"]]
    if not ids:
        return []
    docs = es.mget(index=settings.idx_sessions, ids=ids, source_includes=SESSION_FIELDS)["docs"]
    out = []
    for d in docs:
        if not d.get("found"):
            log.warning("transcript for unknown session %s", d["_id"])
            continue
        s = d["_source"]
        out.append(
            {
                "id": d["_id"],
                "title": s["title"],
                "starts_at": s.get("starts_at"),
                "ends_at": s.get("ends_at"),
                "room": s.get("room"),
                "speakers": s.get("speaker_names") or [],
                "sample": True,
            }
        )
    return sorted(out, key=lambda t: t["starts_at"] or "")


def _summary(session_id: str, title: str, chunks: list[dict]) -> tuple[dict, bool]:
    """The cached summary, or a new one from Claude that is then stored next to the transcript."""
    doc_id = f"summary-{session_id}"
    try:
        cached = es.get(index=settings.idx_transcripts, id=doc_id)["_source"]
        return {"tldr": cached["tldr"], "takeaways": cached["takeaways"]}, True
    except NotFoundError:
        pass

    transcript = "\n\n".join(c["text"] for c in chunks)
    text, usage = llm.complete(
        SUMMARY_SYSTEM,
        [{"role": "user", "content": f"Talk: {title}\n\nTranscript:\n{transcript}"}],
        feature="catchup-summary",
        max_tokens=2048,
        effort="low",
        output_format=SUMMARY_SCHEMA,
    )
    data = json.loads(text)
    summary = {"tldr": data["tldr"].strip(), "takeaways": [t.strip() for t in data["takeaways"]][:3]}
    es.index(
        index=settings.idx_transcripts,
        id=doc_id,
        document={
            "doc_type": "summary",
            "session_id": session_id,
            "sample": True,
            "model": usage.model,
            "created_at": clock.now().isoformat(timespec="seconds"),
            **summary,
        },
    )
    return summary, False


@router.get("/{session_id}")
def talk(session_id: str) -> dict:
    chunks = _transcript_or_404(session_id)
    session = _session(session_id)
    with tracer.start_as_current_span("summary") as span:
        summary, cached = _summary(session_id, session["title"], chunks)
        span.set_attribute("confox.summary.cached", cached)
    return {
        "session": session,
        "sample": True,
        "text": "\n\n".join(c["text"] for c in chunks),
        "chunks": chunks,
        "summary": summary,
        "summary_cached": cached,
    }


def system_prompt(session: dict) -> str:
    return (
        "You answer questions about one conference talk using only its transcript, which is given in numbered "
        "parts. This transcript is a generated sample, not a real recording; mention that if asked about "
        "accuracy. Cite the parts you rely on inline like [2] or [3][5]. Be concise: a short paragraph or a short "
        "list. If the transcript does not cover the question, say so plainly. Plain text only.\n"
        f"Talk: {session['title']} ({when(session['starts_at'], session['ends_at'])}, {session['room']}). "
        f"Speakers: {', '.join(session['speakers']) or 'not listed'}."
    )


@router.post("/{session_id}/ask")
def ask(session_id: str, body: Conversation) -> StreamingResponse:
    with tracer.start_as_current_span("retrieve") as span:
        chunks = _transcript_or_404(session_id)
        session = _session(session_id)
        span.set_attribute("confox.retrieve.transcript_chunks", len(chunks))
    # A keynote transcript is short, so every part goes in; the answer must stay inside this one talk.
    sources = [
        {"n": c["n"], "id": session_id, "title": f"Part {c['n']}", "starts_at": None, "room": None, "kind": "chunk"}
        for c in chunks
    ]
    parts = "\n\n".join(f"[{c['n']}] {c['text']}" for c in chunks)
    question = body.messages[-1].content
    history = [m.model_dump() for m in body.messages[:-1]]
    messages = history + [{"role": "user", "content": f"Transcript parts:\n{parts}\n\nQuestion: {question}"}]
    return StreamingResponse(
        llm.sse_answer(sources, system_prompt(session), messages, feature="catchup"),
        media_type="text/event-stream",
        headers=llm.SSE_HEADERS,
    )
