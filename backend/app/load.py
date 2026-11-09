"""Load the schedule snapshot, speakers, sample attendees, Emma's Monday and sample meetup groups into Elasticsearch.

uv run python -m app.load                 # everything
uv run python -m app.load --only sessions # one index; the others are left alone

With OPENAI_API_KEY set, sessions and people also get an `embedding` vector for semantic search.
"""

import argparse
import json
import logging

from elasticsearch.helpers import bulk
from opentelemetry import trace

from .config import RAW_SCHEDULE, settings
from .data.demo import emma_monday
from .data.groups import sample_groups, sample_posts
from .data.people import sample_attendees, speakers
from .data.samples import attendee_agendas, sample_activity
from .data.sessions import build_sessions
from .embeddings import embed, enabled, join_text, person_text
from .es import es
from .indices import rebuild
from .telemetry import setup_telemetry, shutdown_telemetry

log = logging.getLogger("confox.load")
tracer = trace.get_tracer("confox.load")


def session_text(s: dict) -> str:
    """What a session is about, for its embedding: title, track, projects, then the description."""
    return join_text(s["title"], s.get("track"), s.get("projects"), s.get("description"))


def with_embeddings(docs: list[dict], text) -> list[dict]:
    """Add an `embedding` to each document; unchanged when embeddings are disabled (no key)."""
    if not enabled():
        log.warning("OPENAI_API_KEY not set: indexing without embeddings, search will be keyword only")
        return docs
    vectors = embed([text(d) for d in docs])
    return [d | {"embedding": v} for d, v in zip(docs, vectors, strict=True)]


def _index(index: str, docs: list[dict]) -> int:
    with tracer.start_as_current_span(f"load {index}") as span:
        rebuild(index)
        ok, _ = bulk(
            es, ({"_index": index, "_id": d["id"], "_source": {k: v for k, v in d.items() if k != "id"}} for d in docs)
        )
        es.indices.refresh(index=index)
        span.set_attribute("confox.docs", ok)
        log.info("%s: %d documents", index, ok)
        return ok


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    indices = ["sessions", "people", "agenda", "activity", "groups"]
    parser.add_argument("--only", choices=indices, action="append")
    only = set(parser.parse_args().only or indices)

    setup_telemetry(service_name="confox-load")
    try:
        raw = json.loads(RAW_SCHEDULE.read_text())
        sessions = build_sessions(raw)
        attendees = sample_attendees()
        if "sessions" in only:
            _index(settings.idx_sessions, with_embeddings(sessions, session_text))
        if "people" in only:
            _index(settings.idx_people, with_embeddings(attendees + speakers(raw), person_text))
        agendas = attendee_agendas(sessions, attendees)
        if "agenda" in only:
            _index(settings.idx_agenda, emma_monday(sessions, attendees) + agendas)
        if "activity" in only:
            # Rebuilding drops recorded real events too; that is the point of a reload before a demo.
            _index(settings.idx_activity, sample_activity(attendees, agendas))
        if "groups" in only:
            # Sample meetup groups (and hallway posts); groups created during a demo are dropped.
            _index(settings.idx_groups, sample_groups(sessions, attendees) + sample_posts(attendees))
    finally:
        shutdown_telemetry()


if __name__ == "__main__":
    main()
