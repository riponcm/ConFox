import json

from fastapi.testclient import TestClient

from app.data.transcripts import KEYNOTE_IDS, TRANSCRIPTS_FILE, chunk, chunk_docs
from app.main import app
from app.routers import catchup


def test_chunks_keep_every_word_and_stay_near_200():
    text = "\n\n".join(" ".join(f"w{p}x{i}" for i in range(70)) for p in range(12))  # 840 words
    parts = chunk(text)
    assert sum(len(p.split()) for p in parts) == 840
    assert all(len(p.split()) <= 300 for p in parts)
    assert len(parts) >= 4


def test_committed_transcripts_are_labelled_samples():
    data = json.loads(TRANSCRIPTS_FILE.read_text())
    assert data["sample"] is True
    assert [t["session_id"] for t in data["transcripts"]] == KEYNOTE_IDS
    assert all(t["sample"] and len(t["text"].split()) > 800 for t in data["transcripts"])
    docs = chunk_docs(data["transcripts"])
    assert all(d["sample"] and d["doc_type"] == "chunk" for d in docs)


class FakeES:
    """Just enough Elasticsearch for the summary cache: one transcript, one session, a dict of stored docs."""

    def __init__(self):
        self.stored = {}
        self.indices = self

    def exists(self, index):
        return True

    def search(self, **_kwargs):
        return {"hits": {"hits": [{"_source": {"chunk": 1, "text": "Sandbox every agent."}}]}}

    def get(self, index, id, **_kwargs):
        if index == catchup.settings.idx_sessions:
            return {"_source": {"title": "Sandbox Your Agents", "starts_at": "2026-11-10T09:58:00", "room": "Hall DE"}}
        if id in self.stored:
            return {"_source": self.stored[id]}
        raise catchup.NotFoundError("not found", None, None)

    def index(self, index, id, document):
        self.stored[id] = document


def test_summary_is_generated_once_then_cached(monkeypatch, fake_claude):
    monkeypatch.setattr(catchup, "es", FakeES())
    fake = fake_claude([json.dumps({"tldr": "Sandbox agents.", "takeaways": ["One.", "Two.", "Three."]})])
    client = TestClient(app)
    first = client.get("/api/catchup/1301749").json()
    second = client.get("/api/catchup/1301749").json()
    assert first["summary"] == {"tldr": "Sandbox agents.", "takeaways": ["One.", "Two.", "Three."]}
    assert (first["summary_cached"], second["summary_cached"]) == (False, True)
    assert second["summary"] == first["summary"] and first["sample"] is True
    assert len(fake.calls) == 1
    assert fake.calls[0]["output_config"]["format"]["type"] == "json_schema"
