"""Emma's Monday for the demo: her co-located day, a confirmed coffee with Alice, a pending lunch request."""

DEMO_DAY = "2026-11-09"
COLOCATED_TITLE = "Cloud Native AI + Inference Day"


def emma_monday(sessions: list[dict], people: list[dict]) -> list[dict]:
    day = next(
        s
        for s in sessions
        if s["day"] == DEMO_DAY and s["kind"] == "colocated" and s["title"].startswith(COLOCATED_TITLE)
    )
    coffee = next(s for s in sessions if s["day"] == DEMO_DAY and s["kind"] == "break" and s["title"] == "Coffee Break")
    lunch = next(s for s in sessions if s["day"] == DEMO_DAY and s.get("is_food") and s["title"].startswith("Lunch"))
    requester = next(p for p in people if p["id"] == "att-001")
    base = {"user_id": "emma", "sample": True}
    return [
        base
        | {
            "id": "emma-colocated",
            "kind": "session",
            "status": "confirmed",
            "session_id": day["id"],
            "title": day["title"],
            "starts_at": day["starts_at"],
            "ends_at": day["ends_at"],
            "room": day["room"],
        },
        base
        | {
            "id": "emma-coffee-alice",
            "kind": "meeting",
            "status": "confirmed",
            "with_id": "alice",
            "with_name": "Alice Moreno",
            "title": "Coffee",
            "starts_at": coffee["starts_at"],
            "ends_at": coffee["ends_at"],
            "room": coffee["room"],
        },
        base
        | {
            "id": "emma-lunch-request",
            "kind": "meeting",
            "status": "pending",
            "with_id": requester["id"],
            "with_name": requester["name"],
            "session_id": lunch["id"],
            "room": lunch["room"],
            "title": "Lunch",
            "starts_at": f"{DEMO_DAY}T12:46:00",
            "ends_at": f"{DEMO_DAY}T13:30:00",
        },
    ]
