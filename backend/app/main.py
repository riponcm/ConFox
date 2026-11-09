"""Confox API entry point."""

import logging

from elasticsearch import BadRequestError
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from opentelemetry import trace

from .config import settings
from .es import es
from .routers import include_all
from .telemetry import instrument_app, setup_telemetry

setup_telemetry()

log = logging.getLogger(__name__)

app = FastAPI(title="Confox API")
instrument_app(app)
included = include_all(app)
log.info("routers: %s", ", ".join(included))


def es_reason(exc: BadRequestError) -> str:
    """The most specific reason Elasticsearch gave, e.g. "failed to parse date field [after-lunch] ..."."""
    body = exc.body if isinstance(exc.body, dict) else {}
    err = body.get("error") if isinstance(body.get("error"), dict) else {}
    causes = err.get("root_cause") or []
    if causes and isinstance(causes[0], dict) and causes[0].get("reason"):
        return str(causes[0]["reason"])
    return str(err.get("reason") or exc.message)


@app.exception_handler(BadRequestError)
async def es_bad_request(request: Request, exc: BadRequestError) -> JSONResponse:
    """Elasticsearch rejected the query as invalid (bad date, bad value): that is a client error, not a crash.

    Answer 400 with the reason instead of a 500, keep the cause on the trace and log it as a warning.
    """
    reason = es_reason(exc)
    log.warning("Elasticsearch rejected the query for %s %s: %s", request.method, request.url.path, reason)
    span = trace.get_current_span()
    span.record_exception(exc)
    span.set_attribute("confox.es.rejected_reason", reason)
    return JSONResponse(status_code=400, content={"error": "invalid_query", "detail": reason})


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
