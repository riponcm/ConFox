"""Load the schedule snapshot, speakers, sample attendees and Emma's Monday into Elasticsearch.

uv run python -m app.load                 # everything
uv run python -m app.load --only sessions # one index; the others are left alone
"""

import argparse
import json
import logging

from elasticsearch.helpers import bulk
from opentelemetry import trace

from .config import RAW_SCHEDULE, settings
from .data.demo import emma_monday
from .data.people import sample_attendees, speakers
from .data.sessions import build_sessions
from .es import es
from .indices import rebuild
from .telemetry import setup_telemetry, shutdown_telemetry

log = logging.getLogger("confox.load")
tracer = trace.get_tracer("confox.load")


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
    parser.add_argument("--only", choices=["sessions", "people", "agenda"], action="append")
    only = set(parser.parse_args().only or ["sessions", "people", "agenda"])

    setup_telemetry(service_name="confox-load")
    try:
        raw = json.loads(RAW_SCHEDULE.read_text())
        sessions = build_sessions(raw)
        attendees = sample_attendees()
        if "sessions" in only:
            _index(settings.idx_sessions, sessions)
        if "people" in only:
            _index(settings.idx_people, attendees + speakers(raw))
        if "agenda" in only:
            _index(settings.idx_agenda, emma_monday(sessions, attendees))
    finally:
        shutdown_telemetry()


if __name__ == "__main__":
    main()
