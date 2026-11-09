"""Pure For-you and clash rules, on hand-written sessions; no Elasticsearch."""

from app.routers.schedule import annotate, clashes, for_you, interest_matches, pick_per_slot, truncate

DAY = "2026-11-09"
EMMA = {"interests": ["AI inference", "GPU scheduling", "KServe"], "communities": ["Women in Cloud Native"]}


def session(sid, start, end, title="A talk", kind="talk", **extra):
    return {
        "id": sid,
        "title": title,
        "kind": kind,
        "starts_at": f"{DAY}T{start}:00",
        "ends_at": f"{DAY}T{end}:00",
        "track": extra.pop("track", None),
        "projects": extra.pop("projects", []),
        "description": extra.pop("description", ""),
        "is_food": extra.pop("is_food", False),
        **extra,
    }


COLOCATED = session("day", "09:00", "17:30", "Cloud Native AI + Inference Day", kind="colocated")
COFFEE = session("coffee", "10:48", "11:03", "Coffee Break", kind="break", is_food=True)
AGENDA = [
    {"kind": "session", "status": "confirmed", "session_id": "day", "title": COLOCATED["title"],
     "starts_at": COLOCATED["starts_at"], "ends_at": COLOCATED["ends_at"]},
    {"kind": "meeting", "status": "confirmed", "with_name": "Alice Moreno", "title": "Coffee",
     "starts_at": f"{DAY}T10:48:00", "ends_at": f"{DAY}T11:03:00"},
    {"kind": "meeting", "status": "pending", "with_name": "Liam Haddad", "title": "Lunch",
     "starts_at": f"{DAY}T12:46:00", "ends_at": f"{DAY}T13:30:00"},
]  # fmt: skip


def by_id(sessions):
    return {s["id"]: s for s in sessions}


def test_interest_phrase_is_case_insensitive_and_whole_words():
    assert interest_matches(session("a", "10:00", "10:30", "Scaling ai INFERENCE on GPUs"), ["AI inference"]) == [
        ("AI inference", "title")
    ]
    # "GenAI inference" is not the phrase "AI inference".
    assert interest_matches(session("b", "10:00", "10:30", "GenAI inference tricks"), ["AI inference"]) == []


def test_interest_match_places_rank_title_first():
    s = session("a", "10:00", "10:30", "Serving with KServe", description="Some AI inference notes")
    assert interest_matches(s, ["AI inference", "KServe"]) == [("KServe", "title"), ("AI inference", "description")]
    track_only = session("b", "10:00", "10:30", "Agents everywhere", track="AI Inference + Agentic")
    assert interest_matches(track_only, ["AI inference"]) == [("AI inference", "track")]


def test_for_you_reasons():
    assert for_you(session("k", "09:00", "09:10", "Opening", kind="keynote"), []) == (True, ["keynote"], 0.6)
    assert for_you(COFFEE, []) == (True, ["food and coffee"], 0.5)
    mine, why, fit = for_you(session("t", "11:00", "11:30", "KServe at scale", projects=["KServe"]), EMMA["interests"])
    assert mine and why == ["matches KServe"] and 0.8 < fit <= 0.95
    assert for_you(session("x", "11:00", "11:30", "Gardening"), EMMA["interests"]) == (False, [], 0.0)


def test_for_you_keeps_at_most_two_reasons_agenda_first():
    s = session("t", "11:00", "11:30", "KServe for AI inference", kind="keynote")
    mine, why, fit = for_you(s, EMMA["interests"], on_agenda=True, knn_score=0.8)
    assert mine and why == ["on your agenda", "keynote"] and fit == 1.0


def test_knn_neighbour_is_for_you():
    mine, why, fit = for_you(session("v", "11:00", "11:30", "Unrelated words"), EMMA["interests"], knn_score=0.81)
    assert mine and why == ["close to your interests"] and fit == 0.81


def test_profile_without_interests_or_projects_still_works():
    out = annotate([session("x", "11:00", "11:30", "KServe")], {}, [])
    assert out[0]["for_you"] is False and out[0]["clashes"] == []


def test_colocated_agenda_item_does_not_make_everything_a_clash():
    talk = session("t", "14:00", "14:30", "Something else")
    out = by_id(annotate([COLOCATED, COFFEE, talk], EMMA, AGENDA))
    assert out["t"]["clashes"] == []
    assert out["day"]["on_agenda"] and out["day"]["for_you"] and out["day"]["why"][0] == "on your agenda"


def test_confirmed_meeting_clashes_pending_does_not():
    during_coffee = session("t1", "10:50", "11:00", "Lightning talk")
    during_lunch = session("t2", "12:50", "13:10", "Another talk")
    out = by_id(annotate([COLOCATED, COFFEE, during_coffee, during_lunch], EMMA, AGENDA))
    assert out["t1"]["clashes"] == ["Coffee with Alice Moreno"]
    assert out["t2"]["clashes"] == []
    # The meeting happens at the coffee break, and the full-day event is not one slot: neither is a clash.
    assert out["coffee"]["clashes"] == [] and out["day"]["clashes"] == []


def test_touching_times_do_not_clash():
    blockers = [
        {"status": "confirmed", "title": "Coffee", "starts_at": f"{DAY}T10:48:00", "ends_at": f"{DAY}T11:03:00"}
    ]
    assert clashes(session("t", "11:03", "11:30"), blockers) == []
    assert clashes(session("t", "10:30", "10:49"), blockers) == ["Coffee"]


def test_pick_per_slot_keeps_best_and_strong_second():
    strong_a = {"id": "a", "starts_at": "x", "for_you": True, "fit": 0.9}
    strong_b = {"id": "b", "starts_at": "x", "for_you": True, "fit": 0.85}
    weak = {"id": "c", "starts_at": "x", "for_you": True, "fit": 0.65}
    keynote = {"id": "k", "starts_at": "x", "for_you": True, "fit": 0.6, "kind": "keynote"}
    out = by_id(pick_per_slot([weak, strong_b, strong_a, keynote]))
    assert [out[i]["for_you"] for i in "abck"] == [True, True, False, True]
    lone_weak = {"id": "d", "starts_at": "y", "for_you": True, "fit": 0.5}
    assert pick_per_slot([lone_weak])[0]["for_you"] is True


def test_truncate():
    assert truncate("short") == "short"
    assert len(truncate("x" * 500)) == 300
    assert truncate(None) == ""
