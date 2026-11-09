"""Generated sample behaviour for the 80 sample attendees, so shared views (who is going, what people search)
have something to show. Every document is marked sample=True and seeded, so a reload gives the same data."""

import random

from ..activity import event

SEED = 2026
DEMO_MORNING = ("2026-11-09T07:30:00", "2026-11-09T08:40:00")
ADDABLE = {"keynote", "talk", "lightning", "tutorial", "colocated", "contribfest", "poster"}
SEARCHES = [
    "backstage",
    "cilium",
    "kubeflow",
    "opentelemetry",
    "gpu scheduling",
    "llm inference",
    "ebpf security",
    "platform engineering",
    "argo cd",
    "kserve",
    "cost optimisation",
    "service mesh",
]


def _matches(person: dict, session: dict) -> bool:
    text = " ".join([session.get("title", ""), session.get("track") or "", *session.get("projects", [])]).lower()
    return any(i.lower() in text for i in person.get("interests", []))


def attendee_agendas(sessions: list[dict], attendees: list[dict], skip: tuple[str, ...] = ("emma",)) -> list[dict]:
    """Each sample attendee saves 3 to 6 sessions, mostly ones matching their interests."""
    rng = random.Random(SEED)
    pool = [s for s in sessions if s.get("kind") in ADDABLE and not s.get("is_food")]
    docs = []
    for person in attendees:
        if person["id"] in skip:
            continue
        liked = [s for s in pool if _matches(person, s)]
        picks = rng.sample(liked, min(len(liked), rng.randint(2, 4))) + rng.sample(pool, rng.randint(1, 2))
        for s in {p["id"]: p for p in picks}.values():
            docs.append(
                {
                    "id": f"{person['id']}-s-{s['id']}",
                    "user_id": person["id"],
                    "kind": "session",
                    "status": "confirmed",
                    "session_id": s["id"],
                    "title": s["title"],
                    "starts_at": s["starts_at"],
                    "ends_at": s["ends_at"],
                    "room": s.get("room"),
                    "sample": True,
                }
            )
    return docs


def sample_activity(attendees: list[dict], agendas: list[dict], n: int = 160) -> list[dict]:
    """Events spread over the demo morning: searches, matches, agenda adds, meeting requests and questions."""
    rng = random.Random(SEED + 1)
    start, end = DEMO_MORNING
    first = int(start[11:13]) * 60 + int(start[14:16])
    last = int(end[11:13]) * 60 + int(end[14:16])
    people = [p["id"] for p in attendees if p["id"] != "emma"]
    kinds = ["search"] * 9 + ["match"] * 6 + ["agenda_add"] * 4 + ["connect_request"] + ["question"]
    events = []
    for i in range(n):
        minute = rng.randint(first, last - 1)
        at = f"{start[:11]}{minute // 60:02d}:{minute % 60:02d}:{rng.randint(0, 59):02d}"
        kind = rng.choice(kinds)
        who = rng.choice(people)
        if kind == "search":
            detail = rng.choice(SEARCHES)
        elif kind == "agenda_add":
            own = [a["session_id"] for a in agendas if a["user_id"] == who] or [""]
            detail = rng.choice(own)
        elif kind == "connect_request":
            detail = rng.choice(people)
        else:
            detail = ""
        events.append(event(kind, who, detail, at=at, sample=True) | {"id": f"sample-{i:04d}"})
    return events
