"""Sample meetup groups for the demo, all marked sample=True.

Hosts and members are generated sample attendees who really share the group's value (the Bangladesh meetup is the
exception: no generated attendee is from Bangladesh, so its two members are simply interested). Emma is in none of
them, so she can join, vote and propose her own during the demo. Slots are real food and coffee breaks.
Four hallway board posts by sample attendees, tagged with their own interests, run until late Monday morning.
"""

from datetime import datetime, timedelta

from ..groups_store import new_group, new_post

DEMO_MORNING = "2026-11-09T08:"  # seeded created_at minutes are appended


def _break(sessions: list[dict], day: str, word: str, nth: int = 0) -> dict:
    found = [s for s in sessions if s.get("is_food") and s["day"] == day and word in s["title"].lower()]
    return sorted(found, key=lambda s: s["starts_at"])[nth]


def _sharing(attendees: list[dict], field: str, value: str, n: int) -> list[dict]:
    out = []
    for p in attendees:
        if p["id"] in ("emma", "alice"):
            continue
        v = p.get(field)
        if value == v or (isinstance(v, list) and value in v):
            out.append(p)
    return out[:n]


def _group(gid, host, members, basis, value, title, description, slots, votes, minute):
    g = new_group(gid, host, basis, value, title, description, slots, at=None, sample=True)
    for m in members:
        g["members"].append(m["id"])
        g["member_names"].append(m["name"])
    for slot_index, voters in votes.items():
        g["votes"][g["proposed_slots"][slot_index]["session_id"]] = [p["id"] for p in voters]
    return g | {"created_at": f"{DEMO_MORNING}{minute:02d}:00"}


def sample_groups(sessions: list[dict], attendees: list[dict]) -> list[dict]:
    mon, tue, wed = "2026-11-09", "2026-11-10", "2026-11-11"
    mon_lunch, mon_coffee_pm = _break(sessions, mon, "lunch"), _break(sessions, mon, "coffee", 1)
    tue_coffee, tue_lunch, tue_coffee_pm = (
        _break(sessions, tue, "coffee"),
        _break(sessions, tue, "lunch"),
        _break(sessions, tue, "coffee", 1),
    )
    wed_lunch = _break(sessions, wed, "lunch")

    utah = _sharing(attendees, "schools", "University of Utah", 5)
    wicn = _sharing(attendees, "communities", "Women in Cloud Native", 4)
    kubeflow = _sharing(attendees, "interests", "Kubeflow", 4)
    brazil = _sharing(attendees, "country", "Brazil", 3)
    others = [p for p in attendees if p["id"] not in ("emma", "alice")]
    bangladesh = [others[-1], others[-2]]

    return [
        _group(
            "sample-grp-utah",
            utah[0],
            utah[1:4],
            "school",
            "University of Utah",
            "University of Utah alumni lunch",
            "Utes at KubeCon in our home town. Grab lunch together and swap stories from campus.",
            [mon_lunch, tue_lunch, wed_lunch],
            {0: utah[:3], 1: utah[1:3]},
            5,
        ),
        _group(
            "sample-grp-bangladesh",
            bangladesh[0],
            bangladesh[1:],
            "country",
            "Bangladesh",
            "Bangladesh meetup",
            "From Bangladesh, or with family there? Say hello over coffee.",
            [mon_coffee_pm, tue_coffee],
            {1: bangladesh[:1]},
            12,
        ),
        _group(
            "sample-grp-wicn",
            wicn[0],
            wicn[1:4],
            "community",
            "Women in Cloud Native",
            "Women in Cloud Native coffee",
            "Informal coffee for members and allies. Newcomers to KubeCon very welcome.",
            [mon_coffee_pm, tue_coffee, tue_coffee_pm],
            {0: wicn[:2], 1: wicn[1:4]},
            18,
        ),
        _group(
            "sample-grp-kubeflow",
            kubeflow[0],
            kubeflow[1:3],
            "interest",
            "Kubeflow",
            "Kubeflow users",
            "Running Kubeflow in production? Compare pipelines, notebooks and serving setups.",
            [tue_lunch, wed_lunch],
            {0: kubeflow[:2]},
            24,
        ),
        _group(
            "sample-grp-brazil",
            brazil[0],
            brazil[1:3],
            "country",
            "Brazil",
            "Brasileiros na KubeCon",
            "Everyone from Brazil: lunch and a chat in Portuguese.",
            [tue_lunch, wed_lunch],
            {1: brazil[:3]},
            31,
        ),
    ]


# (minutes after 08:00 on the demo Monday, lasting minutes, interest the author must have, text, place)
POSTS = [
    (5, 180, "Cilium", "At the Cilium booth till 11:00, come talk eBPF and network policy.", "Project Pavilion"),
    (15, 180, "GPU scheduling", "Anyone else fighting GPU fragmentation? Saving seats near the front.", "Room 254"),
    (25, 180, "OpenTelemetry", "Coffee and OpenTelemetry questions by the registration desk.", "Hall A foyer"),
    (32, 180, "Kubeflow", "Kubeflow pipelines on spot nodes: happy to compare notes before lunch.", ""),
]


def sample_posts(attendees: list[dict]) -> list[dict]:
    """Hallway board posts, each by the first sample attendee (not Emma or Alice) into the post's topic."""
    out = []
    for i, (minute, minutes, tag, text, place) in enumerate(POSTS):
        author = next(
            p
            for p in attendees
            if p["id"] not in ("emma", "alice")
            and tag in p.get("interests", [])
            and p["id"] not in {o["author_id"] for o in out}
        )
        at = datetime.fromisoformat(f"{DEMO_MORNING}00:00") + timedelta(minutes=minute)
        out.append(new_post(f"sample-post-{i + 1}", author, text, place, minutes, [tag], at=at, sample=True))
    return out
