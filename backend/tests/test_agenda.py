"""Agenda and Meet rules on hand-written documents; no Elasticsearch."""

from datetime import datetime

from app.agenda_store import (
    clashing_meeting,
    direction,
    free_slots,
    meeting_request,
    meeting_title,
    mirror_request,
    session_doc_id,
    session_item,
    split_agenda,
    split_connect,
    trim_message,
)

MON, TUE, WED = "2026-11-09", "2026-11-10", "2026-11-11"
NOW = datetime.fromisoformat(f"{MON}T08:40:00")


def food(sid, day, start, end, title="Coffee Break"):
    return {"id": sid, "title": title, "starts_at": f"{day}T{start}:00", "ends_at": f"{day}T{end}:00", "room": "Hall"}


FOOD = [
    food("mon-coffee-am", MON, "10:48", "11:03"),
    food("mon-lunch", MON, "12:46", "13:30", "Lunch | On Own"),
    food("mon-coffee-pm", MON, "14:48", "15:03"),
    food("tue-coffee-am", TUE, "10:45", "11:30"),
    food("tue-lunch", TUE, "12:50", "14:50", "Lunch"),
    food("wed-coffee-am", WED, "10:30", "11:00"),
]
COLOCATED = {
    "id": "emma-colocated",
    "kind": "session",
    "status": "confirmed",
    "session_id": "day",
    "starts_at": f"{MON}T09:00:00",
    "ends_at": f"{MON}T17:30:00",
}
COFFEE_ALICE = {
    "id": "emma-coffee-alice",
    "kind": "meeting",
    "status": "confirmed",
    "with_id": "alice",
    "title": "Coffee",
    "starts_at": f"{MON}T10:48:00",
    "ends_at": f"{MON}T11:03:00",
}
LUNCH_REQUEST = {
    "id": "emma-lunch-request",
    "kind": "meeting",
    "status": "pending",
    "with_id": "att-001",
    "title": "Lunch",
    "starts_at": f"{MON}T12:46:00",
    "ends_at": f"{MON}T13:30:00",
}
SEED = [COLOCATED, COFFEE_ALICE, LUNCH_REQUEST]
KINDS = {"day": "colocated"}  # fmt: skip


def ids(slots):
    return [s["session_id"] for s in slots]


def test_slots_skip_taken_breaks_and_ignore_the_colocated_day():
    slots = free_slots(FOOD, SEED, KINDS, "alice", NOW)
    # 10:48 is the confirmed coffee with Alice; the co-located day would block everything if it counted;
    # a pending lunch with someone else does not block.
    assert ids(slots) == ["mon-lunch", "mon-coffee-pm", "tue-coffee-am"]
    assert slots[0] == {
        "session_id": "mon-lunch",
        "title": "Lunch",
        "starts_at": f"{MON}T12:46:00",
        "ends_at": f"{MON}T13:30:00",
        "room": "Hall",
        "day": MON,
    }


def test_slots_skip_a_pending_meeting_with_the_same_person():
    assert "mon-lunch" not in ids(free_slots(FOOD, SEED, KINDS, "att-001", NOW))


def test_slots_skip_a_confirmed_session_that_overlaps():
    talk = {"kind": "session", "status": "confirmed", "session_id": "t1",
            "starts_at": f"{MON}T14:30:00", "ends_at": f"{MON}T15:00:00"}  # fmt: skip
    assert "mon-coffee-pm" not in ids(free_slots(FOOD, [*SEED, talk], KINDS | {"t1": "talk"}, "bob", NOW))


def test_slots_start_now_and_stop_after_the_next_day():
    late = datetime.fromisoformat(f"{MON}T15:30:00")
    assert ids(free_slots(FOOD, [], {}, "bob", late)) == ["tue-coffee-am", "tue-lunch"]
    assert ids(free_slots(FOOD, [], {}, "bob", NOW, limit=10))[-1] == "tue-lunch"


def test_declined_meetings_free_the_slot():
    declined = COFFEE_ALICE | {"status": "declined"}
    assert ids(free_slots(FOOD, [COLOCATED, declined], KINDS, "alice", NOW))[0] == "mon-coffee-am"


def test_meeting_title_from_break_title():
    assert meeting_title("Lunch | On Own") == "Lunch"
    assert meeting_title("Coffee Break") == "Coffee"
    assert meeting_title("Networking Breakfast") == "Breakfast"
    assert meeting_title("Snack | Hall A") == "Snack"


def test_meeting_request_shape_and_message_trim():
    req = meeting_request("emma", FOOD[1], {"id": "alice", "name": "Alice Moreno"}, "  hi \n" + "x" * 300, NOW)
    assert req["status"] == "pending" and req["direction"] == "outgoing" and req["kind"] == "meeting"
    assert req["title"] == "Lunch" and req["with_name"] == "Alice Moreno" and req["session_id"] == "mon-lunch"
    assert req["created_at"] == f"{MON}T08:40:00"
    assert len(req["message"]) == 200 and req["message"].startswith("hi x")
    assert trim_message(None) == ""


def test_session_item_and_id():
    s = {"id": "123", "title": "A talk", "starts_at": f"{TUE}T11:00:00", "ends_at": f"{TUE}T11:30:00", "room": "R"}
    item = session_item("emma", s, NOW)
    assert item["kind"] == "session" and item["status"] == "confirmed" and item["sample"] is False
    assert session_doc_id("emma", "123") == "emma-s-123"


def test_split_connect_treats_missing_direction_as_incoming():
    out = {"id": "o", "kind": "meeting", "status": "pending", "direction": "outgoing", "starts_at": f"{TUE}T10:45:00"}
    gone = LUNCH_REQUEST | {"id": "d", "status": "declined"}
    got = split_connect([*SEED, out, gone])
    assert [m["id"] for m in got["incoming"]] == ["emma-lunch-request"]
    assert [m["id"] for m in got["outgoing"]] == ["o"]
    assert [m["id"] for m in got["meetings"]] == ["emma-coffee-alice"]
    assert direction(LUNCH_REQUEST) == "incoming"


def test_split_agenda_sorts_confirmed_and_lists_pending():
    got = split_agenda([LUNCH_REQUEST, COFFEE_ALICE, COLOCATED])
    assert [i["id"] for i in got["items"]] == ["emma-colocated", "emma-coffee-alice"]
    assert [i["id"] for i in got["pending"]] == ["emma-lunch-request"]


def test_clashing_meeting_only_with_the_same_person():
    assert clashing_meeting(SEED, "alice", f"{MON}T10:48:00", f"{MON}T11:03:00") is COFFEE_ALICE
    assert clashing_meeting(SEED, "bob", f"{MON}T10:48:00", f"{MON}T11:03:00") is None


def test_slots_also_check_the_other_persons_calendar():
    theirs = [{"kind": "meeting", "status": "confirmed", "with_id": "carol", "user_id": "bob",
               "starts_at": f"{MON}T12:46:00", "ends_at": f"{MON}T13:30:00"}]  # fmt: skip
    assert "mon-lunch" in ids(free_slots(FOOD, SEED, KINDS, "bob", NOW))
    assert "mon-lunch" not in ids(free_slots(FOOD, SEED, KINDS, "bob", NOW, other_items=theirs))


def test_mirror_request_is_the_recipients_incoming_copy():
    slot = food("mon-coffee-pm", MON, "14:48", "15:03")
    sent = meeting_request("emma", slot, {"id": "maya", "name": "Maya Martins"}, "hi", NOW, request_id="ab12cd34")
    theirs = mirror_request(sent, {"id": "emma", "name": "Emma Carter"})
    assert theirs["user_id"] == "maya" and theirs["direction"] == "incoming"
    assert theirs["with_id"] == "emma" and theirs["with_name"] == "Emma Carter"
    assert theirs["request_id"] == sent["request_id"] == "ab12cd34"
    assert theirs["starts_at"] == sent["starts_at"] and theirs["status"] == "pending"
