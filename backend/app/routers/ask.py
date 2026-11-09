"""Ask Confox: a question answered by Claude from sessions (and sample transcripts) retrieved from Elasticsearch.

POST /api/ask streams Server-Sent Events: `sources`, then `delta` text chunks, then `done` with tokens and cost.
"""

import re
from datetime import date, datetime, timedelta
from typing import Literal

from elasticsearch import NotFoundError
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from opentelemetry import trace
from pydantic import BaseModel, Field, field_validator

from .. import clock, llm
from ..config import settings
from ..es import es

router = APIRouter(prefix="/api/ask", tags=["ask"])
tracer = trace.get_tracer("confox.ask")

SESSION_HITS = 8
TRANSCRIPT_HITS = 4
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
            return today + timedelta(days=(i - today.weekday()) % 7)
    return None


def search_sessions(question: str, today: date) -> list[dict]:
    day = asked_day(question, today)
    # A named day is a filter; otherwise today gets a small nudge, since questions usually mean "soon".
    by_day = (
        {"filter": {"term": {"day": day.isoformat()}}}
        if day
        else {"should": {"term": {"day": {"value": today.isoformat(), "boost": 1.5}}}}
    )
    r = es.search(
        index=settings.idx_sessions,
        size=SESSION_HITS,
        source_excludes=["embedding"],
        query={
            "bool": {
                "must": {
                    "multi_match": {
                        "query": question,
                        "fields": ["title^3", "speaker_names^2", "projects^2", "track", "description"],
                    }
                },
                "must_not": {"terms": {"kind": NOT_SESSIONS}},
            }
            | by_day
        },
    )
    return [{"id": h["_id"], **h["_source"]} for h in r["hits"]["hits"]]


def search_transcripts(question: str) -> list[dict]:
    if not es.indices.exists(index=settings.idx_transcripts):
        return []
    r = es.search(
        index=settings.idx_transcripts,
        size=TRANSCRIPT_HITS,
        query={"bool": {"must": {"match": {"text": question}}, "filter": {"term": {"doc_type": "chunk"}}}},
    )
    return [h["_source"] for h in r["hits"]["hits"]]


def retrieve(question: str, user_id: str) -> tuple[list[dict], list[str], dict]:
    """Sources for the answer: numbered entries for the browser and the matching context lines for Claude."""
    with tracer.start_as_current_span("retrieve") as span:
        sessions = search_sessions(question, clock.now().date())
        chunks = search_transcripts(question)
        titles = {}
        if chunks:
            ids = list({c["session_id"] for c in chunks})
            docs = es.mget(index=settings.idx_sessions, ids=ids, source_includes=["title"])["docs"]
            titles = {d["_id"]: d["_source"]["title"] for d in docs if d.get("found")}
        user = profile(user_id)
        span.set_attribute("confox.retrieve.sessions", len(sessions))
        span.set_attribute("confox.retrieve.transcript_chunks", len(chunks))

    sources, context = [], []
    for s in sessions:
        n = len(sources) + 1
        sources.append(
            {"n": n, "id": s["id"], "title": s["title"], "starts_at": s.get("starts_at"), "room": s.get("room")}
            | {"kind": s.get("kind")}
        )
        details = [
            when(s.get("starts_at"), s.get("ends_at")),
            s.get("room") or "room not set",
            s.get("kind") or "",
            "Speakers: " + ", ".join(s.get("speaker_names") or []) if s.get("speaker_names") else "",
            f"Track: {s['track']}" if s.get("track") else "",
            "Projects: " + ", ".join(s["projects"]) if s.get("projects") else "",
        ]
        desc = (s.get("description") or "").replace("\n", " ")[:600]
        context.append(f"[{n}] {s['title']} | " + " | ".join(d for d in details if d) + (f"\n{desc}" if desc else ""))
    for c in chunks:
        n = len(sources) + 1
        title = titles.get(c["session_id"], "a keynote")
        sources.append(
            {"n": n, "id": c["session_id"], "title": f"Sample transcript: {title}", "starts_at": None, "room": None}
            | {"kind": "transcript", "chunk": c["chunk"]}
        )
        context.append(f"[{n}] Sample transcript (generated) of '{title}', part {c['chunk']}:\n{c['text']}")
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
        "stand-ins, not the speaker's actual words; say so if you use one. "
        "If the sources do not answer the question, say that plainly instead "
        "of guessing. Plain text only, no headings."
    )


@router.post("")
def ask(body: AskBody) -> StreamingResponse:
    question = body.messages[-1].content
    sources, context, user = retrieve(question, body.user_id)
    history = [m.model_dump() for m in body.messages[:-1]]
    latest = "Sources:\n" + ("\n\n".join(context) or "(none found)") + f"\n\nQuestion: {question}"
    messages = history + [{"role": "user", "content": latest}]
    return StreamingResponse(
        llm.sse_answer(sources, system_prompt(user), messages, feature="ask"),
        media_type="text/event-stream",
        headers=llm.SSE_HEADERS,
    )
