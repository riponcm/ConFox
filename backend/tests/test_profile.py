"""Profile editing: validation, the stored document, embeddings and suggestions. No Elasticsearch, no OpenAI."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import embeddings
from app.main import app
from app.routers import profile as pr

STORED = {
    "name": "Emma Carter",
    "title": "Platform Engineer",
    "company": "Wasatch Cloud",
    "bio": "Runs the internal platform for ML teams.",
    "interests": ["AI inference", "Kubeflow"],
    "interests_text": "AI inference, Kubeflow",
    "schools": ["University of Utah"],
    "city": "Salt Lake City",
    "country": "United States",
    "kind": "attendee",
    "sample": True,
}


def form(**changes) -> dict:
    base = {k: v for k, v in pr.editable(STORED).items()}
    return base | changes


def test_valid_profile_is_trimmed_and_deduplicated():
    p = pr.ProfileIn(**form(name=" Emma ", interests=["eBPF", "ebpf", " GitOps "], links=["https://github.com/emma"]))
    assert p.name == "Emma" and p.interests == ["eBPF", "GitOps"] and p.links == ["https://github.com/emma"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", " "),
        ("bio", "b" * 501),
        ("looking_for", "x" * 201),
        ("interests", [f"topic {i}" for i in range(13)]),
        ("interests", ["x" * 41]),
        ("interests", [""]),
        ("links", ["https://a.dev", "https://b.dev", "https://c.dev", "https://d.dev"]),
        ("links", ["github.com/emma"]),
        ("links", ["ftp://example.com"]),
        ("visibility", "friends"),
        ("embedding", [0.1]),
        ("kind", "speaker"),
    ],
)
def test_invalid_values_are_refused(field, value):
    with pytest.raises(ValidationError) as err:
        pr.ProfileIn(**form(**{field: value}))
    assert err.value.errors()[0]["loc"][0] == field


def test_editable_fills_defaults():
    out = pr.editable({"name": "X"})
    assert out["interests"] == [] and out["looking_for"] == "" and out["visibility"] == "public"
    assert set(out) == set(pr.EDITABLE)


def test_build_doc_keeps_other_fields_and_rebuilds_interests_text():
    update = pr.ProfileIn(**form(interests=["AI inference", "eBPF"], projects=["Cilium"], tracks=["Security"]))
    doc = pr.build_doc(STORED | {"embedding": [1.0]}, update, "2026-11-09T08:41:00")
    assert doc["interests_text"] == "AI inference, eBPF, Cilium, Security"
    assert doc["kind"] == "attendee" and doc["sample"] is True and "embedding" not in doc
    assert doc["updated_at"] == "2026-11-09T08:41:00"
    assert pr.changed_fields(STORED, doc) == ["interests", "projects", "tracks"]
    assert pr.changed_fields(STORED, pr.build_doc(STORED, pr.ProfileIn(**form()), "t")) == []


def test_embedding_is_recomputed_only_when_the_text_changes():
    same = pr.build_doc(STORED, pr.ProfileIn(**form(schools=["University of Utah", "BUET"])), "t")
    assert pr.embedding_plan(STORED, same, has_vector=True, enabled=True) == "unchanged"
    new_topic = pr.build_doc(STORED, pr.ProfileIn(**form(interests=["eBPF"])), "t")
    assert pr.embedding_plan(STORED, new_topic, has_vector=True, enabled=True) == "updated"
    assert pr.embedding_plan(STORED, new_topic, has_vector=True, enabled=False) == "skipped"
    assert pr.embedding_plan(STORED, same, has_vector=False, enabled=True) == "updated"
    assert embeddings.person_text(new_topic).splitlines()[3] == "eBPF"  # same recipe as the loader


def test_options_rank_by_count_with_utah_first():
    def terms(*keys):
        return {"buckets": [{"key": k, "doc_count": 10 - i} for i, k in enumerate(keys)]}

    people = {
        "attendees": {"interests": terms("eBPF", "GitOps")},
        "schools": terms("TU Munich", "BUET", "University of Utah"),
        "company": terms("Google", "Wasatch Cloud"),
        "past_companies": {"buckets": [{"key": "Wasatch Cloud", "doc_count": 30}]},
        "communities": terms("CNCF Ambassadors"),
        "city": terms("Tokyo"),
        "country": terms("Japan"),
    }
    sessions = {"tracks": terms("Maintainer Track", "Registration", "Security", "Breaks"), "projects": terms("Cilium")}
    out = pr.parse_options(people, sessions)
    assert out["schools"] == ["University of Utah", "TU Munich", "BUET"]
    assert out["companies"] == ["Wasatch Cloud", "Google"]
    assert out["tracks"] == ["Maintainer Track", "Security"]
    assert out["interests"] == ["eBPF", "GitOps"] and out["projects"] == ["Cilium"]
    assert pr.unknown_tracks(["Security", "Made up"], out["tracks"]) == ["Made up"]


class FakeES:
    """Just enough Elasticsearch for a save: the stored doc, the track list and the write."""

    def __init__(self, vector=None):
        self.source = STORED | ({"embedding": vector} if vector else {})
        self.written: dict | None = None
        self.indices = self

    def get(self, index, id, **kw):
        if id != "emma":
            from elasticsearch import NotFoundError

            raise NotFoundError("not found", meta=None, body={})
        return {"_id": id, "_source": dict(self.source)}

    def search(self, index, size, aggs):
        return {"aggregations": {"tracks": {"buckets": [{"key": "Security", "doc_count": 3}]}}}

    def put_mapping(self, index, properties):
        self.mapping = properties

    def index(self, index, id, document, refresh):
        self.written = {"id": id, "document": document, "refresh": refresh}


def test_save_without_key_writes_with_refresh_and_says_so(monkeypatch):
    fake = FakeES(vector=[0.5, 0.5])
    monkeypatch.setattr(pr, "es", fake)
    monkeypatch.setattr(embeddings.settings, "openai_api_key", "")
    body = form(interests=["AI inference", "eBPF"], tracks=["Security"])
    r = TestClient(app).put("/api/profile/emma", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert (
        out["changed"] == ["interests", "tracks"] and out["embedding"] == "skipped" and "OPENAI_API_KEY" in out["note"]
    )
    assert out["profile"]["has_embedding"] is False and out["profile"]["interests"] == ["AI inference", "eBPF"]
    assert fake.written["refresh"] == "wait_for" and "embedding" not in fake.written["document"]
    assert fake.written["document"]["interests_text"] == "AI inference, eBPF, Security"
    assert "tracks" in fake.mapping


def test_save_keeps_the_vector_when_the_text_is_the_same(monkeypatch):
    fake = FakeES(vector=[0.5, 0.5])
    monkeypatch.setattr(pr, "es", fake)
    monkeypatch.setattr(embeddings, "embed", lambda texts: pytest.fail("no embedding call for a school change"))
    r = TestClient(app).put("/api/profile/emma", json=form(schools=["University of Utah", "BUET"]))
    assert r.json()["embedding"] == "unchanged" and fake.written["document"]["embedding"] == [0.5, 0.5]


def test_save_embeds_new_text(monkeypatch):
    fake = FakeES(vector=[0.5, 0.5])
    monkeypatch.setattr(pr, "es", fake)
    monkeypatch.setattr(embeddings.settings, "openai_api_key", "test-key-not-real")
    monkeypatch.setattr(embeddings, "embed", lambda texts: [[0.1, 0.9]] if "eBPF" in texts[0] else [])
    r = TestClient(app).put("/api/profile/emma", json=form(interests=["eBPF"]))
    assert r.json()["embedding"] == "updated" and fake.written["document"]["embedding"] == [0.1, 0.9]


def test_save_refuses_unknown_tracks_and_users(monkeypatch):
    fake = FakeES()
    monkeypatch.setattr(pr, "es", fake)
    client = TestClient(app)
    r = client.put("/api/profile/emma", json=form(tracks=["Made up"]))
    assert r.status_code == 422 and r.json()["detail"][0]["loc"] == ["body", "tracks"]
    assert client.put("/api/profile/nobody", json=form()).status_code == 403  # only the signed-in user can save
    assert client.put("/api/profile/emma", json=form(bio="b" * 501)).status_code == 422
    assert fake.written is None


def test_only_the_signed_in_user_can_save_a_profile():
    from fastapi.testclient import TestClient

    from app.main import app

    r = TestClient(app).put("/api/profile/alice", json={"name": "Mallory"})
    assert r.status_code == 403
