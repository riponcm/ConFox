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


def test_asked_day_picks_the_nearest_weekday():
    wednesday = date(2026, 11, 11)
    assert ask.asked_day("What did the Tuesday keynotes say?", wednesday) == date(2026, 11, 10)
    assert ask.asked_day("Anything on Thursday?", MONDAY) == date(2026, 11, 12)
    assert ask.asked_day("What happened on Sunday?", MONDAY) == date(2026, 11, 8)


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


# Retrieval: query bodies, fusion, source numbering.
VEC = [0.1, 0.2, 0.3]
SESSION = {"id": "s1", "title": "Cheap GPUs", "starts_at": "2026-11-09T10:00:00", "ends_at": "2026-11-09T10:30:00"} | {
    "room": "Hall A",
    "kind": "talk",
    "speaker_names": ["Ana"],
}
ALICE = {"id": "alice", "name": "Alice Moreno", "title": "ML Engineer", "company": "Redwood Labs"} | {
    "interests": ["GPU scheduling", "eBPF"],
    "sample": True,
    "bio": "Builds schedulers.",
}
BOB = {"id": "bob", "name": "Bob Ito", "title": "Maintainer", "company": None, "sample": False}


def test_plan_hybrid_is_one_native_rrf_body_per_index_plus_transcripts():
    reqs = ask.plan("GPU scheduling today", "emma", MONDAY, VEC, "hybrid", True)
    assert [i for i, _ in reqs] == ["confox-sessions", "confox-people", "confox-transcripts"]
    sessions, people = reqs[0][1], reqs[1][1]
    rrf = sessions["retriever"]["rrf"]
    assert rrf["rank_constant"] == 60 and sessions["size"] == ask.SESSION_HITS
    knn = rrf["retrievers"][1]["knn"]
    assert knn["query_vector"] == VEC and knn["field"] == "embedding"
    # "today" is a filter on both the BM25 and the kNN side, and breaks are excluded on both.
    lexical = rrf["retrievers"][0]["standard"]["query"]["bool"]
    assert {"term": {"day": "2026-11-09"}} in lexical["filter"] and lexical["filter"] == knn["filter"]
    assert {"bool": {"must_not": {"terms": {"kind": ["break", "registration"]}}}} in knn["filter"]
    p_rrf = people["retriever"]["rrf"]
    fields = p_rrf["retrievers"][0]["standard"]["query"]["bool"]["must"]["multi_match"]["fields"]
    assert "name^3" in fields and "interests_text^2" in fields and "bio" in fields
    assert {"terms": {"kind": ["speaker", "attendee"]}} in p_rrf["retrievers"][1]["knn"]["filter"]
    assert {"bool": {"must_not": {"ids": {"values": ["emma"]}}}} in p_rrf["retrievers"][1]["knn"]["filter"]
    assert "embedding" in sessions["_source"]["excludes"]


def test_plan_without_a_named_day_nudges_today_instead_of_filtering():
    q = ask.plan("kubeflow", "emma", MONDAY, None, "bm25", False)[0][1]["query"]["bool"]
    assert q["should"] == [{"term": {"day": {"value": "2026-11-09", "boost": 1.5}}}]
    assert not any("term" in f for f in q["filter"])


def test_plan_bm25_has_no_retriever_or_knn():
    reqs = ask.plan("ebpf", "emma", MONDAY, None, "bm25", True)
    assert [i for i, _ in reqs] == ["confox-sessions", "confox-people", "confox-transcripts"]
    assert all("retriever" not in b and "knn" not in b for _, b in reqs)


def test_plan_client_side_has_a_bm25_and_a_knn_body_per_index():
    reqs = ask.plan("ebpf", "emma", MONDAY, VEC, "hybrid-client", False)
    assert [i for i, _ in reqs] == ["confox-sessions"] * 2 + ["confox-people"] * 2
    assert "query" in reqs[0][1] and "knn" in reqs[1][1] and "query" in reqs[2][1] and "knn" in reqs[3][1]


def hit(i):
    return {"_id": i, "_source": {"name": i}}


def resp(*ids):
    return {"hits": {"hits": [hit(i) for i in ids]}}


def test_collect_fuses_client_side_lists_with_rrf():
    responses = [resp("a", "b"), resp("b", "c"), resp("p1"), resp("p2", "p1"), resp()]
    sessions, people, chunks = ask.collect(responses, "hybrid-client", True, True)
    assert [s["id"] for s in sessions] == ["b", "a", "c"]  # b is in both lists, so it wins
    assert [p["id"] for p in people] == ["p1", "p2"]
    assert chunks == []


def test_collect_native_reads_in_plan_order():
    chunk = {"_id": "c", "_source": {"session_id": "s1", "chunk": 2, "text": "t"}}
    responses = [resp("s1"), resp("alice"), {"hits": {"hits": [chunk]}}]
    sessions, people, chunks = ask.collect(responses, "hybrid", True, True)
    assert [s["id"] for s in sessions] == ["s1"] and [p["id"] for p in people] == ["alice"]
    assert chunks == [{"session_id": "s1", "chunk": 2, "text": "t"}]


def test_person_context_marks_sample_people_and_never_adds_contacts():
    line = ask.person_context(7, ALICE)
    assert line.startswith("[7] Person: Alice Moreno, ML Engineer at Redwood Labs; interests: GPU scheduling, eBPF;")
    assert "sample attendee" in line and "@" not in line
    assert ask.person_context(2, BOB) == "[2] Person: Bob Ito, Maintainer; speaker"


def test_build_sources_numbers_sessions_then_people_then_chunks():
    chunk = {"session_id": "s1", "chunk": 3, "text": "words"}
    sources, context = ask.build_sources([SESSION], [ALICE, BOB], [chunk], {"s1": "Cheap GPUs"})
    assert [s["n"] for s in sources] == [1, 2, 3, 4]
    assert [s["kind"] for s in sources] == ["session", "person", "person", "transcript"]
    assert sources[0]["session_kind"] == "talk" and sources[0]["room"] == "Hall A"
    assert sources[1] == {"n": 2, "kind": "person", "id": "alice", "name": "Alice Moreno"} | {
        "title": "ML Engineer",
        "company": "Redwood Labs",
        "sample": True,
        "starts_at": None,
        "room": None,
    }
    assert sources[2]["sample"] is False
    assert sources[3]["chunk"] == 3 and sources[3]["title"] == "Sample transcript: Cheap GPUs"
    assert context[0].startswith("[1] Cheap GPUs | Mon 9 Nov 10:00-10:30 | Hall A")
    assert context[1].startswith("[2] Person: Alice Moreno") and context[3].startswith("[4] Sample transcript")


def test_system_prompt_lets_claude_recommend_people_but_not_invent_contacts():
    text = ask.system_prompt({"name": "Emma Carter", "interests": ["AI inference"], "schools": ["University of Utah"]})
    assert "recommend people to meet" in text and "sample attendee" in text and "Never invent contact" in text
    assert "interests: AI inference" in text and "school: University of Utah" in text


def test_run_retrieval_falls_back_to_client_rrf_without_a_licence(monkeypatch):
    calls = []

    def fake_msearch(reqs):
        calls.append(len(reqs))
        if len(reqs) == 2:
            raise ask.search.SearchFailed(
                {"type": "security_exception", "reason": "current license is non-compliant for [rrf]"}
            )
        return [resp("s1"), resp("s2"), resp("alice"), resp("bob")]

    monkeypatch.setattr(ask.search, "msearch", fake_msearch)
    monkeypatch.setattr(ask.search, "_native_rrf", None)
    mode, sessions, people, chunks = ask.run_retrieval("gpu", "emma", MONDAY, VEC, False)
    assert mode == "hybrid-client" and calls == [2, 4]
    assert [s["id"] for s in sessions] == ["s1", "s2"] and [p["id"] for p in people] == ["alice", "bob"]
    assert not ask.search.native_rrf_ok()
    monkeypatch.setattr(ask.search, "_native_rrf", None)


def test_run_retrieval_without_a_key_is_bm25(monkeypatch):
    monkeypatch.setattr(ask.search, "msearch", lambda reqs: [resp("s1"), resp("alice")])
    assert ask.run_retrieval("gpu", "emma", MONDAY, None, False)[0] == "bm25"


def test_query_vector_is_none_without_a_key(monkeypatch):
    monkeypatch.setattr(ask.embeddings.settings, "openai_api_key", "")
    assert ask.query_vector("gpu") is None
