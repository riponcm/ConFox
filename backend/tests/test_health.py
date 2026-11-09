import logging

from fastapi.testclient import TestClient

from app import main
from app.main import app


def test_health_answers_without_elasticsearch():
    r = TestClient(app).get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_logs_elasticsearch_failure(monkeypatch, caplog):
    class Unreachable:
        def options(self, **_kwargs):
            return self

        @property
        def cluster(self):
            raise ConnectionError("connection refused")

    monkeypatch.setattr(main, "es", Unreachable())
    with caplog.at_level(logging.WARNING):
        r = TestClient(app).get("/api/health")
    assert r.json() == {"status": "ok", "elasticsearch": "unreachable"}
    assert "connection refused" in caplog.text
