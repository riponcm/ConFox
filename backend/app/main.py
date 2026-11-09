"""Confox API entry point."""

import logging

from elasticsearch import Elasticsearch
from fastapi import FastAPI
from opentelemetry import trace

from .config import settings

log = logging.getLogger(__name__)

app = FastAPI(title="Confox API")
es = Elasticsearch(settings.es_url, request_timeout=5)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness for the API plus a cheap reachability check on Elasticsearch.

    An Elasticsearch failure does not fail the endpoint (the API itself is up), but it is logged with the
    cause and recorded on the current span. The span is a no-op until telemetry is wired up in pull request 1.
    """
    try:
        es_status = es.cluster.health()["status"]
    except Exception as exc:
        log.warning("Elasticsearch health check failed: %s", exc, exc_info=exc)
        trace.get_current_span().record_exception(exc)
        es_status = "unreachable"
    return {"status": "ok", "elasticsearch": es_status}
