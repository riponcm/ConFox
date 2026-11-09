from app.routers.now import (
    build_slots,
    choose_featured,
    group_slots,
    known_people,
    minutes_until,
    parse_going,
    pick_next,
    pick_then,
    split_now,
)


def s(id_, start, end, kind="talk", food=False):
    return {"id": id_, "starts_at": start, "ends_at": end, "kind": kind, "is_food": food}


def test_split_now_orders_and_filters():
    sessions = [
        s("day", "2026-11-09T09:00:00", "2026-11-09T17:30:00", kind="colocated"),
        s("lt", "2026-11-09T08:30:00", "2026-11-09T09:30:00"),
        s("coffee", "2026-11-09T08:30:00", "2026-11-09T09:00:00", kind="break", food=True),
        s("next", "2026-11-09T09:40:00", "2026-11-09T09:45:00"),
        s("later", "2026-11-09T11:00:00", "2026-11-09T11:30:00"),
    ]
    on, soon = split_now(sessions, "2026-11-09T09:10:00", "2026-11-09T10:40:00")
    assert [x["id"] for x in on] == ["lt", "day"]  # food is shown separately; full-day events go last
    assert [x["id"] for x in soon] == ["next"]


# ---------- next, then, slots and featured (hand-written data, no Elasticsearch) ----------


D = "2026-11-09T"
NOW = D + "08:40:00"


def item(id_, type_, start, end, **kw):
    return {"id": id_, "type": type_, "title": kw.pop("title", id_), "starts_at": D + start, "ends_at": D + end,
            "room": "Salt Palace | Level 2 | 254", **kw}  # fmt: skip


DAY = item("emma-colocated", "session", "09:00:00", "17:30:00", session_id="ai-day", all_day=True,
           title="Cloud Native AI + Inference Day")  # fmt: skip
COFFEE = item("emma-coffee-alice", "meeting", "10:48:00", "11:03:00", title="Coffee", with_name="Alice Moreno")
LUNCH = item("lunch", "food", "12:46:00", "13:30:00", session_id="lunch")


def test_minutes_until():
    assert minutes_until(NOW, D + "09:00:00") == 20
    assert minutes_until(NOW, D + "10:48:00") == 128


def test_next_is_first_agenda_item_not_started_and_then_is_the_one_after():
    timeline = [DAY, COFFEE, LUNCH]
    nxt = pick_next(timeline, [], NOW)
    assert (nxt["id"], nxt["minutes_from_now"], nxt["source"]) == ("emma-colocated", 20, "agenda")
    then = pick_then(timeline, nxt, NOW)
    assert (then["id"], then["with_name"], then["minutes_from_now"]) == ("emma-coffee-alice", "Alice Moreno", 128)


def test_started_all_day_event_is_skipped_and_food_counts_for_then():
    timeline = [DAY, COFFEE, LUNCH]
    at = D + "09:10:00"
    nxt = pick_next(timeline, [], at)
    assert nxt["id"] == "emma-coffee-alice"
    assert pick_then(timeline, nxt, at)["id"] == "lunch"
    assert pick_then(timeline, nxt, at)["source"] == "food"


def test_meeting_in_progress_is_still_next():
    nxt = pick_next([DAY, COFFEE], [], D + "10:50:00")
    assert nxt["id"] == "emma-coffee-alice" and nxt["minutes_from_now"] == -2


def test_next_falls_back_to_earliest_best_for_you_session():
    annotated = [
        {"id": "b", "title": "B", "starts_at": D + "09:30:00", "ends_at": D + "10:00:00", "for_you": True, "fit": 0.6},
        {
            "id": "a",
            "title": "A",
            "starts_at": D + "09:30:00",
            "ends_at": D + "10:00:00",
            "for_you": True,
            "fit": 0.9,
            "why": ["matches KServe"],
        },
        {"id": "c", "title": "C", "starts_at": D + "09:00:00", "ends_at": D + "10:00:00", "for_you": False},
        {
            "id": "k",
            "title": "Coffee",
            "starts_at": D + "09:00:00",
            "ends_at": D + "09:15:00",
            "for_you": True,
            "kind": "break",
            "is_food": True,
        },
        {"id": "old", "title": "Old", "starts_at": D + "08:00:00", "ends_at": D + "09:00:00", "for_you": True},
    ]
    nxt = pick_next([LUNCH], annotated, NOW)  # food alone never counts as "where to be next"
    assert (nxt["id"], nxt["source"], nxt["why"]) == ("a", "for_you", ["matches KServe"])
    assert pick_then([LUNCH], nxt, NOW)["id"] == "lunch"
    assert pick_next([], [], NOW) is None
    assert pick_then([LUNCH], None, NOW)["id"] == "lunch"


def ses(id_, start, **kw):
    return {"id": id_, "title": kw.pop("title", id_), "starts_at": D + start, "ends_at": D + "11:00:00", **kw}


def test_group_slots_by_start_within_horizon_breaks_apart():
    sessions = [
        ses("on", "08:30:00"),
        ses("t1", "09:00:00"),
        ses("t2", "09:00:00"),
        ses("cb", "09:00:00", kind="break", is_food=True),
        ses("t3", "10:40:00"),
        ses("late", "10:41:00"),
        ses("reg", "09:00:00", kind="registration"),
    ]
    groups = group_slots(sessions, NOW, D + "10:40:00")
    assert [(start[11:16], food, [x["id"] for x in g]) for start, food, g in groups] == [
        ("09:00", False, ["t1", "t2"]),
        ("09:00", True, ["cb"]),
        ("10:40", False, ["t3"]),
    ]


def test_featured_prefers_agenda_then_for_you_then_most_going():
    a = ses("a", "09:00:00", for_you=True, fit=0.9)
    b = ses("b", "09:00:00", on_agenda=True)
    c = ses("c", "09:00:00")
    going = {"c": 5}
    assert choose_featured([a, b, c], going) == (b, ["on your agenda"])
    assert choose_featured([a, c], going)[0] is a
    assert choose_featured([c], going) == (c, ["popular with attendees"])
    assert choose_featured([ses("d", "09:00:00")], going) == (None, [])
    assert choose_featured([ses("e", "09:00:00", kind="break", is_food=True, on_agenda=True)], {}) == (None, [])


def test_build_slots_shapes_featured_and_others():
    sessions = [
        ses("mine", "09:00:00", on_agenda=True, title="Cloud Native AI + Inference Day Hosted by CNCF | ALL ACCESS"),
        ses("x", "09:00:00"),
        ses("y", "09:00:00", description="long text"),
        ses("quiet", "09:30:00"),
        ses("cb", "10:00:00", kind="break", is_food=True),
    ]
    slots = build_slots(sessions, {"mine": 2, "y": 3}, {"mine": ["Alice", "Liam", "Maya"]}, NOW, D + "10:40:00")
    first = slots[0]
    assert (first["minutes_from_now"], first["food"]) == (20, False)
    f = first["featured"]
    assert (f["id"], f["short_title"], f["going"], f["friends"], f["why"]) == (
        "mine", "Cloud Native AI + Inference Day", 2, ["Alice", "Liam"], ["on your agenda"],
    )  # fmt: skip
    assert [(o["id"], o["going"]) for o in first["others"]] == [("y", 3), ("x", 0)]  # most going first
    assert "description" not in first["others"][0]
    assert slots[1]["featured"] is None and [o["id"] for o in slots[1]["others"]] == ["quiet"]
    assert slots[2]["food"] is True and slots[2]["featured"] is None


def test_known_people_meetings_first_then_matches_without_self_or_declined():
    agenda = [
        {"kind": "meeting", "status": "confirmed", "with_id": "alice", "with_name": "Alice Moreno"},
        {"kind": "meeting", "status": "pending", "with_id": "att-001", "with_name": "Liam Haddad"},
        {"kind": "meeting", "status": "declined", "with_id": "att-009", "with_name": "Nope"},
        {"kind": "session", "status": "confirmed", "session_id": "x"},
    ]
    ranked = [{"id": "att-071", "name": "Aisha Martins"}, {"id": "alice", "name": "Alice"}, {"id": "emma"}]
    assert known_people(agenda, ranked, "emma") == {
        "alice": "Alice Moreno", "att-001": "Liam Haddad", "att-071": "Aisha Martins",
    }  # fmt: skip


def test_parse_going_orders_friends_by_how_well_the_user_knows_them():
    aggs = {
        "going": {"buckets": [{"key": "s1", "doc_count": 5}, {"key": "s2", "doc_count": 1}]},
        "known": {"sessions": {"buckets": [
            {"key": "s1", "users": {"buckets": [{"key": "att-071", "doc_count": 1}, {"key": "alice", "doc_count": 1}]}},
        ]}},
    }  # fmt: skip
    going, friends = parse_going(aggs, {"alice": "Alice Moreno", "att-071": "Aisha Martins"})
    assert going == {"s1": 5, "s2": 1}
    assert friends == {"s1": ["Alice Moreno", "Aisha Martins"]}
    assert parse_going({}, {}) == ({}, {})
