import json
from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.routers import ask

MONDAY = date(2026, 11, 9)
SOURCES = [{"n": 1, "id": "s1", "title": "Cheap GPUs", "starts_at": "2026-11-09T10:00:00", "room": "A", "kind": "talk"}]


def events(body: str) -> list[dict]:
    return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]


def test_asked_day():
    assert ask.asked_day("Which talks today are about GPUs?", MONDAY) == MONDAY
    assert ask.asked_day("anything tomorrow on eBPF", MONDAY) == date(2026, 11, 10)
    assert ask.asked_day("What is on Wednesday?", MONDAY) == date(2026, 11, 11)
    assert ask.asked_day("Who knows about KServe?", MONDAY) is None


def test_ask_streams_sources_then_text_then_usage(monkeypatch, fake_claude, spans):
    monkeypatch.setattr(ask, "retrieve", lambda q, u: (SOURCES, ["[1] Cheap GPUs"], {"name": "Emma Carter"}))
    fake = fake_claude(["Go to ", "Cheap GPUs [1]."])
    r = TestClient(app).post("/api/ask", json={"messages": [{"role": "user", "content": "GPU talks today?"}]})
    assert r.status_code == 200
    ev = events(r.text)
    assert [e["type"] for e in ev] == ["sources", "delta", "delta", "done"]
    assert ev[0]["sources"] == SOURCES
    assert ev[-1]["usage"]["input_tokens"] == 1000 and ev[-1]["usage"]["cost_usd"] > 0
    sent = fake.calls[0]["messages"][-1]["content"]
    assert "[1] Cheap GPUs" in sent and sent.endswith("Question: GPU talks today?")
    assert "Monday 9 November, 08:40" in fake.calls[0]["system"]
    assert any(s.name == "chat claude-opus-5-5" for s in spans.get_finished_spans())


def test_ask_reports_a_failed_answer(monkeypatch, fake_claude):
    monkeypatch.setattr(ask, "retrieve", lambda q, u: (SOURCES, [], {}))
    fake = fake_claude(["x"])

    def boom(**_kwargs):
        raise RuntimeError("overloaded")

    fake_async = ask.llm._async
    fake_async.beta.messages.stream = boom
    r = TestClient(app).post("/api/ask", json={"messages": [{"role": "user", "content": "q"}]})
    assert [e["type"] for e in events(r.text)] == ["sources", "error"]
    assert fake.calls == []


def test_ask_needs_a_user_question_last():
    body = {"messages": [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]}
    assert TestClient(app).post("/api/ask", json=body).status_code == 422
