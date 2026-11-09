"""Meetup group rules on hand-written documents: ranking, suggestions, votes, joining, fixing. No Elasticsearch."""

from datetime import datetime

import pytest

from app.data.groups import sample_groups, sample_posts
from app.groups_store import (
    GroupError,
    agenda_item,
    board,
    fix,
    join,
    leading_slot,
    leave,
    match_reason,
    new_group,
    new_post,
    rank,
    remove_check,
    suggest_aggs,
    suggestions,
    tally,
    view,
    vote,
)

AT = datetime.fromisoformat("2026-11-09T08:40:00")
EMMA = {
    "id": "emma",
    "name": "Emma Carter",
    "company": "Wasatch Cloud",
    "past_companies": ["Copperleaf"],
    "schools": ["University of Utah"],
    "communities": ["Women in Cloud Native"],
    "interests": ["AI inference", "Kubeflow"],
    "country": "United States",
}
HOST = {"id": "att-002", "name": "Maya Okafor"}


def brk(sid, start, end, title="Coffee Break"):
    return {"id": sid, "title": title, "starts_at": f"2026-11-09T{start}:00", "ends_at": f"2026-11-09T{end}:00"}


LUNCH = brk("lunch", "12:46", "13:30", "Lunch | On Own") | {"room": "Ballroom"}
COFFEE = brk("coffee-pm", "14:48", "15:03")
EARLY = brk("coffee-am", "10:48", "11:03")


def group(gid="g1", basis="school", value="University of Utah", slots=(LUNCH, COFFEE), **kw):
    return new_group(gid, HOST, basis, value, "", "", list(slots), at=AT, **kw)


# ---------- creating ----------


def test_new_group_sorts_slots_names_itself_and_starts_open_with_the_host():
    g = group(slots=(COFFEE, LUNCH))
    assert [s["session_id"] for s in g["proposed_slots"]] == ["lunch", "coffee-pm"]
    assert g["proposed_slots"][0] == {
        "session_id": "lunch",
        "title": "Lunch",
        "starts_at": "2026-11-09T12:46:00",
        "ends_at": "2026-11-09T13:30:00",
        "room": "Ballroom",
    }
    assert g["title"] == "University of Utah alumni meetup"
    assert g["members"] == ["att-002"] and g["member_names"] == ["Maya Okafor"]
    assert g["status"] == "open" and g["fixed_slot"] is None
    assert g["votes"] == {"lunch": [], "coffee-pm": []}
    assert g["created_at"] == "2026-11-09T08:40:00"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"basis": "planet"},
        {"value": "   "},
        {"slots": ()},
        {"slots": (LUNCH, LUNCH)},
        {"slots": (EARLY, LUNCH, COFFEE, brk("x", "16:00", "16:30"))},
    ],
)
def test_new_group_refuses_bad_input(kwargs):
    with pytest.raises(GroupError) as err:
        group(**kwargs)
    assert err.value.status == 422


def test_max_members_is_clamped():
    assert group(max_members=1)["max_members"] == 2
    assert group(max_members=999)["max_members"] == 50


# ---------- ranking ----------


def test_match_reason_needs_the_same_basis():
    assert match_reason(group(), EMMA) == {
        "basis": "school",
        "value": "University of Utah",
        "label": "You studied at University of Utah",
    }
    assert match_reason(group(basis="company", value="Copperleaf"), EMMA)["label"] == "You work or worked at Copperleaf"
    assert match_reason(group(basis="country", value="University of Utah"), EMMA) is None
    assert match_reason(group(basis="country", value="Bangladesh"), EMMA) is None


def test_rank_puts_matching_groups_first_by_basis_then_size_and_splits_mine():
    bangladesh = group("bd", "country", "Bangladesh")
    bangladesh = join(join(join(bangladesh, "a", "A"), "b", "B"), "c", "C")  # biggest, but no match
    kubeflow = group("kf", "interest", "Kubeflow")
    wicn = group("wicn", "community", "Women in Cloud Native")
    utah = group("utah")
    mine = join(group("us", "country", "United States"), "emma", "Emma Carter")
    out = rank([bangladesh, kubeflow, wicn, utah, mine], "emma", EMMA)
    assert [g["id"] for g in out["groups"]] == ["utah", "wicn", "kf", "bd"]
    assert [g["id"] for g in out["mine"]] == ["us"]
    assert out["groups"][0]["match"]["label"] == "You studied at University of Utah"
    assert out["groups"][-1]["match"] is None and out["groups"][-1]["member_count"] == 4
    assert out["mine"][0]["is_member"] and not out["mine"][0]["is_host"]


def test_suggestions_count_people_per_value_most_telling_basis_first():
    aggs = suggest_aggs("emma", EMMA)
    assert set(aggs) == {"school", "country", "company", "community", "interest"}
    assert aggs["company"]["filters"]["filters"]["Copperleaf"]["bool"]["should"][1] == {
        "term": {"past_companies": "Copperleaf"}
    }
    counts = {
        "school": {"University of Utah": 8},
        "country": {"United States": 40},
        "company": {"Wasatch Cloud": 12, "Copperleaf": 0},
        "community": {"Women in Cloud Native": 20},
        "interest": {"AI inference": 30, "Kubeflow": 15},
    }
    result = {b: {"buckets": {v: {"doc_count": c} for v, c in vs.items()}} for b, vs in counts.items()}
    existing = [group("utah")]
    out = suggestions(EMMA, result, existing)
    assert [s["value"] for s in out] == [
        "University of Utah",
        "United States",
        "Women in Cloud Native",
        "Wasatch Cloud",
        "AI inference",
        "Kubeflow",
    ]
    assert out[0]["label"] == "University of Utah · 8 people here"
    assert out[0]["existing"] == ["utah"] and out[1]["existing"] == []
    assert "_order" not in out[0]
    assert len(suggestions(EMMA, result, [], limit=2)) == 2


# ---------- votes ----------


def test_vote_tally_and_leading_slot():
    g = join(join(group(), "emma", "Emma Carter"), "b", "B")
    assert leading_slot(g) is None
    g = vote(g, "emma", "coffee-pm")
    g = vote(g, "b", "coffee-pm")
    g = vote(g, "b", "lunch")
    g = vote(g, "b", "lunch")  # voting twice counts once
    assert [(s["session_id"], s["votes"], s["voted"]) for s in tally(g, "emma")] == [
        ("lunch", 1, False),
        ("coffee-pm", 2, True),
    ]
    assert leading_slot(g) == "coffee-pm"
    g = vote(g, "emma", "coffee-pm", on=False)
    assert leading_slot(g) == "lunch"  # tie at one vote each: the earlier time leads


def test_vote_does_not_mutate_the_original():
    g = join(group(), "emma", "Emma Carter")
    vote(g, "emma", "lunch")
    assert g["votes"]["lunch"] == []


@pytest.mark.parametrize(
    ("user", "session", "status"),
    [("stranger", "lunch", 403), ("emma", "nope", 422)],
)
def test_vote_rules(user, session, status):
    g = join(group(), "emma", "Emma Carter")
    with pytest.raises(GroupError) as err:
        vote(g, user, session)
    assert err.value.status == status


def test_no_votes_once_fixed():
    g = fix(join(group(), "emma", "Emma Carter"), "att-002", "lunch")
    with pytest.raises(GroupError) as err:
        vote(g, "emma", "coffee-pm")
    assert err.value.status == 409


# ---------- join and leave ----------


def test_join_is_idempotent_and_respects_the_limit():
    g = group(max_members=2)
    g = join(g, "emma", "Emma Carter")
    assert join(g, "emma", "Emma Carter") is g
    with pytest.raises(GroupError) as err:
        join(g, "c", "C")
    assert err.value.status == 409
    assert view(g, "emma")["spots_left"] == 0


def test_leave_removes_member_name_and_votes_but_not_the_host():
    g = vote(join(group(), "emma", "Emma Carter"), "emma", "lunch")
    g = leave(g, "emma")
    assert g["members"] == ["att-002"] and g["member_names"] == ["Maya Okafor"]
    assert g["votes"]["lunch"] == []
    assert leave(g, "emma") is g
    with pytest.raises(GroupError) as err:
        leave(g, "att-002")
    assert err.value.status == 409


# ---------- fixing ----------


def test_only_the_host_fixes_once_and_only_a_proposed_time():
    g = join(group(), "emma", "Emma Carter")
    for user, session, status in [("emma", "lunch", 403), ("att-002", "coffee-am", 422)]:
        with pytest.raises(GroupError) as err:
            fix(g, user, session)
        assert err.value.status == status
    fixed = fix(g, "att-002", "lunch")
    assert fixed["status"] == "fixed" and fixed["fixed_slot"]["session_id"] == "lunch"
    with pytest.raises(GroupError) as err:
        fix(fixed, "att-002", "coffee-pm")
    assert err.value.status == 409


def test_fixed_group_gives_members_a_confirmed_agenda_meeting():
    g = fix(join(group(sample=True), "emma", "Emma Carter"), "att-002", "lunch")
    item = agenda_item(g, "emma", at=AT)
    assert item == {
        "id": "emma-g-g1",
        "user_id": "emma",
        "kind": "meeting",
        "status": "confirmed",
        "group_id": "g1",
        "with_id": "g1",
        "with_name": "University of Utah alumni meetup",
        "session_id": "lunch",
        "title": "Meetup: University of Utah alumni meetup",
        "starts_at": "2026-11-09T12:46:00",
        "ends_at": "2026-11-09T13:30:00",
        "room": "Ballroom",
        "sample": False,  # Emma's own item is real; sample members' items are sample
        "created_at": "2026-11-09T08:40:00",
    }
    assert agenda_item(g, "att-002", at=AT)["sample"] is True


# ---------- seed ----------


def _session(sid, day, start, end, title):
    return {"id": sid, "day": day, "is_food": True, "title": title, "starts_at": f"{day}T{start}:00",
            "ends_at": f"{day}T{end}:00", "room": "Hall"}  # fmt: skip


def test_sample_groups_are_labelled_and_consistent():
    sessions = []
    for day in ("2026-11-09", "2026-11-10", "2026-11-11"):
        sessions += [
            _session(f"{day}-c1", day, "10:30", "11:00", "Coffee Break"),
            _session(f"{day}-l", day, "12:30", "13:30", "Lunch"),
            _session(f"{day}-c2", day, "15:00", "15:30", "Coffee Break"),
        ]
    attendees = [{"id": "emma", "name": "Emma"}, {"id": "alice", "name": "Alice"}]
    attendees += [
        {
            "id": f"att-{i:03d}",
            "name": f"Person {i}",
            "schools": ["University of Utah"],
            "communities": ["Women in Cloud Native"],
            "interests": ["Kubeflow"],
            "country": "Brazil",
        }
        for i in range(1, 7)
    ]
    groups = sample_groups(sessions, attendees)
    assert [g["title"] for g in groups][:4] == [
        "University of Utah alumni lunch",
        "Bangladesh meetup",
        "Women in Cloud Native coffee",
        "Kubeflow users",
    ]
    for g in groups:
        assert g["sample"] is True and g["status"] == "open"
        assert "emma" not in g["members"] and len(g["members"]) == len(g["member_names"])
        assert g["members"][0] == g["host_id"]
        assert all(set(v) <= set(g["members"]) for v in g["votes"].values())
        assert set(g["votes"]) == {s["session_id"] for s in g["proposed_slots"]}


# ---------- hallway board ----------


def test_new_post_trims_keeps_only_own_interests_and_expires():
    author = EMMA | {"interests": ["AI inference", "Kubeflow", "KServe", "vLLM", "GPU scheduling"]}
    p = new_post("p1", author, "  At the   Kubeflow booth " + "x" * 200, "Hall B", 30, ["Kubeflow", "Cilium"], at=AT)
    assert p["text"].startswith("At the Kubeflow booth x") and len(p["text"]) == 140
    assert p["tags"] == ["Kubeflow"]
    assert (p["type"], p["author_id"], p["place"]) == ("post", "emma", "Hall B")
    assert (p["created_at"], p["expires_at"]) == ("2026-11-09T08:40:00", "2026-11-09T09:10:00")
    many = new_post("p2", author, "hi", tags=["vLLM", "KServe", "AI inference", "Kubeflow"], at=AT)
    assert many["tags"] == ["AI inference", "Kubeflow", "KServe"]  # profile order, at most three


@pytest.mark.parametrize(("text", "minutes"), [("   ", 60), ("hi", 45)])
def test_new_post_refuses_empty_text_and_odd_lengths(text, minutes):
    with pytest.raises(GroupError) as err:
        new_post("p", EMMA, text, minutes=minutes, at=AT)
    assert err.value.status == 422


def test_board_highlights_matches_hides_expired_and_mixes_in_groups():
    later = datetime.fromisoformat("2026-11-09T08:50:00")
    mine = new_post("p-mine", EMMA, "Here", minutes=30, tags=["Kubeflow"], at=AT)
    other = new_post(
        "p-other", HOST | {"interests": ["Cilium"]}, "Cilium booth", minutes=180, tags=["Cilium"], at=later
    )
    gone = new_post("p-gone", HOST, "Old news", minutes=30, at=datetime.fromisoformat("2026-11-09T08:00:00"))
    done = fix(group("done", slots=(EARLY,)), "att-002", "coffee-am")
    feed = board(
        [mine, other, gone], [group("utah"), done], "emma", EMMA, datetime.fromisoformat("2026-11-09T12:00:00")
    )
    assert [i["id"] for i in feed] == ["utah"]  # posts expired, fixed group over; the open group stays
    feed = board([mine, other, gone], [group("utah"), done], "emma", EMMA, later)
    assert [(i["id"], i["kind"], i["for_you"]) for i in feed] == [
        ("p-other", "post", False),  # newest first; same-minute items by id
        ("utah", "group", True),
        ("p-mine", "post", True),
        ("done", "group", True),
    ]
    assert feed[2]["mine"] and not feed[0]["mine"] and feed[2]["matching"] == ["Kubeflow"]


def test_only_the_author_removes_a_post():
    p = new_post("p", EMMA, "hi", at=AT)
    remove_check(p, "emma")
    with pytest.raises(GroupError) as err:
        remove_check(p, "att-002")
    assert err.value.status == 403
    with pytest.raises(GroupError) as err:
        remove_check(group(), "att-002")
    assert err.value.status == 404


def test_sample_posts_are_tagged_with_their_authors_interests():
    attendees = [{"id": "emma", "name": "Emma", "interests": ["Kubeflow"]}]
    attendees += [
        {"id": f"att-{i}", "name": f"P{i}", "interests": ["Cilium", "GPU scheduling", "OpenTelemetry", "Kubeflow"]}
        for i in range(4)
    ]
    posts = sample_posts(attendees)
    assert len(posts) == 4 and all(p["sample"] and p["type"] == "post" for p in posts)
    assert len({p["author_id"] for p in posts}) == 4 and "emma" not in {p["author_id"] for p in posts}
    assert all(p["tags"] and p["expires_at"] > "2026-11-09T08:40:00" for p in posts)


def test_busy_at_finds_a_confirmed_item_at_the_meetup_time(monkeypatch):
    from app.routers import groups as router

    slot = {"starts_at": "2026-11-09T14:48:00", "ends_at": "2026-11-09T15:03:00"}
    items = [
        {"id": "emma-g-g1", "status": "confirmed", "starts_at": slot["starts_at"], "ends_at": slot["ends_at"]},
        {
            "id": "emma-colocated",
            "status": "confirmed",
            "session_id": "day",
            "starts_at": "2026-11-09T09:00:00",
            "ends_at": "2026-11-09T17:30:00",
        },  # fmt: skip
    ]
    monkeypatch.setattr(router.agenda, "user_items", lambda uid: items)
    monkeypatch.setattr(router.agenda, "session_kinds", lambda ids: {"day": "colocated"})
    # Its own meetup item and the co-located day do not count, so the user is free.
    assert router._busy_at("emma", slot, "g1") is None
    coffee = {"id": "emma-coffee", "status": "confirmed", "title": "Coffee", **slot}
    monkeypatch.setattr(router.agenda, "user_items", lambda uid: [*items, coffee])
    assert router._busy_at("emma", slot, "g1")["title"] == "Coffee"
