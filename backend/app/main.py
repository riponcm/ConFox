"""Confox API entry point."""

import logging

from fastapi import FastAPI, HTTPException
from opentelemetry import trace

from .config import settings
from .es import es
from .telemetry import instrument_app, setup_telemetry

setup_telemetry()

log = logging.getLogger(__name__)

app = FastAPI(title="Confox API")
instrument_app(app)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness for the API plus a cheap reachability check on Elasticsearch.

    An Elasticsearch failure does not fail the endpoint (the API itself is up), but it is logged with the
    cause and recorded on the current span.
    """
    try:
        es_status = es.options(request_timeout=5).cluster.health()["status"]
    except Exception as exc:
        log.warning("Elasticsearch health check failed: %s", exc, exc_info=exc)
        trace.get_current_span().record_exception(exc)
        es_status = "unreachable"
    return {"status": "ok", "elasticsearch": es_status}


@app.post("/api/debug/break")
def debug_break(mode: str = "es") -> dict[str, str]:
    """Trigger a real failure so the demo can show Dash0 finding it. Disabled unless ENABLE_DEBUG_ENDPOINTS=true.

    mode=es sends Elasticsearch a range query with a value that is not a date, which Elasticsearch rejects:
    the error, its span and its log line are all real, not simulated.
    """
    if not settings.enable_debug_endpoints:
        raise HTTPException(status_code=404)
    if mode != "es":
        raise HTTPException(status_code=400, detail="unknown mode")
    log.error("debug break requested: sending an invalid range query to Elasticsearch")
    es.search(index=settings.idx_sessions, query={"range": {"starts_at": {"gte": "after-lunch"}}}, size=1)
    return {"status": "unexpectedly ok"}
