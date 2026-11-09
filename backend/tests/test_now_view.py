from app.routers.now import split_now


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
