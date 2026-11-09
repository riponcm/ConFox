"""Confox API entry point."""

from elasticsearch import Elasticsearch
from fastapi import FastAPI

from .config import settings

app = FastAPI(title="Confox API")
es = Elasticsearch(settings.es_url, request_timeout=5)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness for the API plus a cheap reachability check on Elasticsearch."""
    try:
        es_status = es.cluster.health()["status"]
    except Exception:
        es_status = "unreachable"
    return {"status": "ok", "elasticsearch": es_status}
