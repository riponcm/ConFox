from app.routers.brief import (
    build_summary,
    build_timeline,
    find_gaps,
    free_food,
    mark_next,
    pick_people,
    pick_suggested,
    short_title,
    split_requests,
)

DAY = "2026-11-09"
NOW = f"{DAY}T08:40:00"


def t(hhmm: str, day: str = DAY) -> str:
    return f"{day}T{hhmm}:00"


AI_DAY = {
    "id": "1289760",
    "title": "Cloud Native AI + Inference Day Hosted by CNCF - Full Day Event | ALL ACCESS PASS REQUIRED",
    "kind": "colocated",
    "day": DAY,
    "starts_at": t("09:00"),
    "ends_at": t("17:30"),
    "room": "Salt Palace | Level 2 | 254",
}
COFFEE = {"id": "c1", "title": "Coffee Break", "kind": "break", "is_food": True, "day": DAY,
          "starts_at": t("10:48"), "ends_at": t("11:03"), "room": "Hyatt | Ballroom"}  # fmt: skip
LUNCH = {"id": "l1", "title": "Lunch | On Own", "kind": "break", "is_food": True, "day": DAY,
         "starts_at": t("12:46"), "ends_at": t("13:30"), "room": "Hyatt | Ballroom"}  # fmt: skip
COFFEE_PM = {"id": "c2", "title": "Coffee Break", "kind": "break", "is_food": True, "day": DAY,
             "starts_at": t("14:48"), "ends_at": t("15:03"), "room": "Hyatt | Ballroom"}  # fmt: skip
SESSIONS = [AI_DAY, COFFEE, LUNCH, COFFEE_PM]

AGENDA = [
    {"id": "emma-colocated", "kind": "session", "status": "confirmed", "session_id": "1289760",
     "title": AI_DAY["title"], "starts_at": t("09:00"), "ends_at": t("17:30"), "room": AI_DAY["room"]},
    {"id": "emma-coffee-alice", "kind": "meeting", "status": "confirmed", "with_id": "alice",
     "with_name": "Alice Moreno", "title": "Coffee", "starts_at": t("10:48"), "ends_at": t("11:03"),
     "room": "Hyatt | Ballroom"},
    {"id": "emma-lunch-request", "kind": "meeting", "status": "pending", "with_id": "att-001",
     "with_name": "Liam Haddad", "title": "Lunch", "starts_at": t("12:46"), "ends_at": t("13:30")},
]  # fmt: skip


def timeline():
    return mark_next(build_timeline(AGENDA, SESSIONS, DAY), NOW)


def test_short_title_drops_host_and_pass_notes():
    assert short_title(AI_DAY["title"]) == "Cloud Native AI + Inference Day"
    assert short_title("Lunch | On Own") == "Lunch"
    assert short_title("Plain") == "Plain"


def test_timeline_merges_sorted_and_skips_break_taken_by_meeting():
    items = timeline()
    assert [(i["type"], i["starts_at"][11:16]) for i in items] == [
        ("session", "09:00"),
        ("meeting", "10:48"),
        ("food", "12:46"),
        ("food", "14:48"),
    ]
    assert items[0]["all_day"] is True
    assert items[0]["title"] == "Cloud Native AI + Inference Day"
    assert items[0]["full_title"] == AI_DAY["title"]
    assert items[1]["with_name"] == "Alice Moreno"
    # The pending lunch request is not on the timeline; the lunch break is.
    assert all(i["status"] != "pending" for i in items)


def test_timeline_ignores_other_days_and_declined():
    other = AGENDA + [
        {"id": "x", "kind": "meeting", "status": "declined", "starts_at": t("16:00"), "ends_at": t("16:30")},
        {"id": "y", "kind": "meeting", "status": "confirmed", "starts_at": t("10:00", "2026-11-10"),
         "ends_at": t("10:30", "2026-11-10")},
    ]  # fmt: skip
    ids = [i["id"] for i in build_timeline(other, SESSIONS, DAY)]
    assert "x" not in ids and "y" not in ids


def test_is_next_is_first_item_not_ended():
    items = timeline()
    assert [i["is_next"] for i in items] == [True, False, False, False]


def test_is_next_skips_all_day_event_already_under_way():
    items = mark_next(build_timeline(AGENDA, SESSIONS, DAY), t("11:00"))
    # 11:00: the AI day is running and coffee with Alice has not ended yet.
    assert [i["id"] for i in items if i["is_next"]] == ["emma-coffee-alice"]
    items = mark_next(items, t("11:10"))
    assert [i["id"] for i in items if i["is_next"]] == ["l1"]


def test_is_next_falls_back_to_all_day_event_when_nothing_else_is_left():
    items = mark_next(build_timeline(AGENDA, SESSIONS, DAY), t("16:00"))
    assert [i["id"] for i in items if i["is_next"]] == ["emma-colocated"]
    items = mark_next(items, t("18:00"))
    assert not any(i["is_next"] for i in items)


def test_gaps_ignore_all_day_events_and_start_at_now():
    gaps = find_gaps(timeline(), DAY, NOW)
    assert [(g["starts_at"][11:16], g["ends_at"][11:16], g["minutes"]) for g in gaps] == [
        ("08:40", "10:48", 128),
        ("11:03", "12:46", 103),
        ("13:30", "14:48", 78),
        ("15:03", "19:00", 237),
    ]


def test_gaps_skip_short_windows_and_handle_overlaps():
    items = [
        {"starts_at": t("08:00"), "ends_at": t("10:00")},
        {"starts_at": t("09:00"), "ends_at": t("11:30")},  # overlaps the first
        {"starts_at": t("12:00"), "ends_at": t("18:30")},  # 30 minutes before: too short
    ]
    gaps = find_gaps(items, DAY, t("07:00"))
    assert [(g["starts_at"][11:16], g["ends_at"][11:16]) for g in gaps] == []
    items[-1]["ends_at"] = t("17:00")
    assert [(g["starts_at"][11:16], g["ends_at"][11:16]) for g in find_gaps(items, DAY, t("07:00"))] == [
        ("17:00", "19:00")
    ]


def test_gaps_on_another_day_use_the_whole_window():
    gaps = find_gaps([], DAY, t("20:00", "2026-11-08"))
    assert gaps == [{"starts_at": t("08:00"), "ends_at": t("19:00"), "minutes": 660}]
    assert find_gaps([], DAY, t("18:30")) == []


def test_requests_split_by_direction_and_borrow_food_room():
    agenda = AGENDA + [
        {"id": "out", "kind": "meeting", "status": "pending", "direction": "outgoing", "with_id": "bob",
         "with_name": "Bob", "title": "Coffee", "starts_at": t("14:48"), "ends_at": t("15:03"), "room": "R"},
    ]  # fmt: skip
    req = split_requests(agenda, DAY, SESSIONS)
    assert [r["id"] for r in req["incoming"]] == ["emma-lunch-request"]
    assert req["incoming"][0]["room"] == "Hyatt | Ballroom"
    assert req["incoming"][0]["direction"] == "incoming"
    assert [r["id"] for r in req["outgoing"]] == ["out"]


def test_free_food_skips_breaks_with_confirmed_meetings():
    free = free_food(SESSIONS, timeline(), NOW, DAY)
    assert free and free["starts_at"] == t("12:46")
    assert free_food(SESSIONS, timeline(), t("13:00"), DAY)["starts_at"] == t("14:48")
    assert free_food(SESSIONS, timeline(), t("15:00"), DAY) is None


def test_summary_from_data():
    items = timeline()
    req = split_requests(AGENDA, DAY, SESSIONS)
    assert build_summary(items, req, NOW) == (
        "Your day centres on Cloud Native AI + Inference Day from 09:00. Coffee with Alice Moreno at 10:48. "
        "1 meeting request is waiting for you."
    )


def test_summary_without_plans():
    assert build_summary([], {"incoming": [], "outgoing": []}, NOW) == "Nothing is planned for the rest of today yet."
    req = {"incoming": [{}, {}], "outgoing": [{}]}
    assert build_summary([], req, NOW) == "2 meeting requests are waiting for you. You are waiting on 1 reply."


def test_suggested_only_unstarted_interest_matches_off_agenda():
    def s(sid, start, **kw):
        return {"id": sid, "kind": "lightning", "starts_at": t(start), "ends_at": t(start), "for_you": True,
                "on_agenda": False, "clashes": [], "why": ["matches KServe"], "fit": 0.85} | kw  # fmt: skip

    annotated = [
        s("past", "08:30"),
        s("kserve", "10:36"),
        s("agenda", "11:00", on_agenda=True),
        s("clash", "10:50", clashes=["Coffee with Alice"]),
        s("keynote", "11:10", why=["keynote"]),
        s("colo", "12:00", kind="colocated"),
        s("food", "12:46", is_food=True, kind="break"),
        s("weak", "13:00", fit=0.5, why=["close to your interests"]),
        s("llm", "11:52", fit=0.9),
        s("extra", "14:00", fit=0.4),
    ]
    assert [x["id"] for x in pick_suggested(annotated, NOW)] == ["kserve", "llm", "weak"]


def test_people_skip_met_and_carry_one_reason():
    user = {"schools": ["University of Utah"], "interests": ["KServe"]}
    ranked = [
        {"id": "alice", "name": "Alice", "schools": ["University of Utah"]},
        {"id": "p1", "name": "P One", "schools": ["University of Utah"], "interests": ["KServe"], "sample": True},
        {"id": "p2", "name": "P Two", "interests": ["KServe"]},
        {"id": "p3", "name": "P Three"},
        {"id": "p4", "name": "P Four"},
    ]
    free = {"starts_at": t("12:46")}
    people = pick_people(user, ranked, {"alice"}, free)
    assert [p["id"] for p in people] == ["p1", "p2", "p3"]
    assert people[0]["reason"] == "University of Utah alumni"
    assert people[1]["reason"] == "Both into KServe"
    assert people[2]["reason"] == ""
    assert people[0]["free_at"] == free and people[0]["sample"] is True
