from fastapi.testclient import TestClient

from app import clock
from app.main import app, included


def test_routers_are_discovered():
    assert "meta" in included


def test_meta_uses_the_demo_clock(monkeypatch):
    monkeypatch.setattr(clock.settings, "demo_now", "2026-11-09T08:40:00")
    assert TestClient(app).get("/api/meta").json() == {"now": "2026-11-09T08:40:00", "user_id": "emma"}


def test_real_clock_when_demo_now_is_empty(monkeypatch):
    monkeypatch.setattr(clock.settings, "demo_now", "")
    assert clock.now().tzinfo is None
