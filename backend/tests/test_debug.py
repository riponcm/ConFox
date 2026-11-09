from fastapi.testclient import TestClient

from app import main
from app.main import app


def test_break_is_hidden_by_default(monkeypatch):
    monkeypatch.setattr(main.settings, "enable_debug_endpoints", False)
    assert TestClient(app).post("/api/debug/break").status_code == 404


def test_break_raises_the_elasticsearch_error(monkeypatch):
    monkeypatch.setattr(main.settings, "enable_debug_endpoints", True)

    def reject(**_kwargs):
        raise RuntimeError("failed to parse date field [after-lunch]")

    monkeypatch.setattr(main.es, "search", reject)
    r = TestClient(app, raise_server_exceptions=False).post("/api/debug/break?mode=es")
    assert r.status_code == 500
