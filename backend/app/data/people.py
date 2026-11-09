"""People: public speaker profiles from the schedule, plus generated sample attendees.

Real attendee profiles are private, so attendees are fictional and marked sample=True. Generation is seeded, so
every load produces the same people. The demo persona Emma and her best match Alice share University of Utah.
"""

import random

from .sessions import TRACK_CATEGORY, speaker_company, strip_emoji

SEED = 2026
SCHOOLS = [
    "University of Utah",
    "Utah State University",
    "Brigham Young University",
    "University of Washington",
    "Georgia Tech",
    "UC Berkeley",
    "University of Toronto",
    "IIT Bombay",
    "TU Munich",
    "University of São Paulo",
]
PLACES = [
    ("Salt Lake City", "United States"),
    ("Seattle", "United States"),
    ("Austin", "United States"),
    ("San Francisco", "United States"),
    ("Toronto", "Canada"),
    ("Bengaluru", "India"),
    ("Berlin", "Germany"),
    ("London", "United Kingdom"),
    ("São Paulo", "Brazil"),
    ("Tokyo", "Japan"),
]
COMPANIES = ["Wasatch Cloud", "Redwood Labs", "Northbeam", "Harborline", "Copperleaf", "Bluefin Data", "Lumen Grid"]
TITLES = ["Platform Engineer", "SRE", "Software Engineer", "ML Engineer", "DevOps Lead", "Engineering Manager"]
COMMUNITIES = ["CNCF Ambassadors", "Women in Cloud Native", "Kubernetes contributors", "Local meetup organisers"]
FIRST = ["Maya", "Liam", "Sofia", "Noah", "Aisha", "Mateo", "Hana", "Ethan", "Priya", "Lucas", "Zara", "Diego"]
LAST = ["Nguyen", "Okafor", "Martins", "Kowalski", "Tanaka", "Haddad", "Fischer", "Raman", "Silva", "Brooks"]
INTERESTS = [
    "AI inference",
    "GPU scheduling",
    "Platform engineering",
    "Observability",
    "eBPF",
    "Service mesh",
    "Supply chain security",
    "GitOps",
    "Multi-cluster",
    "Autoscaling",
    "Developer portals",
    "Cost optimisation",
]
PROJECTS = ["Kubeflow", "KServe", "vLLM", "Argo", "Flux", "Cilium", "OpenTelemetry", "Backstage", "Envoy", "Keda"]

EMMA = {
    "id": "emma",
    "name": "Emma Carter",
    "title": "Platform Engineer",
    "company": "Wasatch Cloud",
    "bio": "First KubeCon. Runs the internal platform for ML teams and wants cheaper, faster inference on Kubernetes.",
    "interests": ["AI inference", "GPU scheduling", "Platform engineering", "Kubeflow", "KServe"],
    "schools": ["University of Utah"],
    "past_companies": ["Copperleaf"],
    "communities": ["Women in Cloud Native"],
    "city": "Salt Lake City",
    "country": "United States",
}
ALICE = {
    "id": "alice",
    "name": "Alice Moreno",
    "title": "ML Engineer",
    "company": "Redwood Labs",
    "bio": "Serves LLMs on shared GPU clusters. Happy to compare notes on KServe and vLLM.",
    "interests": ["AI inference", "GPU scheduling", "KServe", "vLLM"],
    "schools": ["University of Utah"],
    "past_companies": ["Wasatch Cloud"],
    "communities": ["Kubernetes contributors"],
    "city": "Salt Lake City",
    "country": "United States",
}


def _person(base: dict) -> dict:
    return base | {"kind": "attendee", "sample": True, "interests_text": ", ".join(base["interests"])}


def sample_attendees(n: int = 80) -> list[dict]:
    """Emma, Alice, then n-2 seeded attendees. University of Utah alumni are listed first."""
    rng = random.Random(SEED)
    people = [_person(EMMA), _person(ALICE)]
    used = {EMMA["name"], ALICE["name"]}
    i = 0
    while len(people) < n:
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        if name in used:
            continue
        used.add(name)
        i += 1
        city, country = rng.choice(PLACES)
        interests = rng.sample(INTERESTS, 3) + rng.sample(PROJECTS, 2)
        people.append(
            _person(
                {
                    "id": f"att-{i:03d}",
                    "name": name,
                    "title": rng.choice(TITLES),
                    "company": rng.choice(COMPANIES),
                    "bio": f"Works on {interests[0].lower()} and {interests[3]}.",
                    "interests": interests,
                    "schools": [rng.choice(SCHOOLS)],
                    "past_companies": rng.sample(COMPANIES, 1),
                    "communities": rng.sample(COMMUNITIES, rng.randint(0, 2)),
                    "city": city,
                    "country": country,
                }
            )
        )
    head, rest = people[:2], people[2:]
    rest.sort(key=lambda p: p["schools"][0] != "University of Utah")  # stable: Utah alumni first
    return head + rest


def speakers(raw: dict) -> list[dict]:
    """Public speaker profiles as published on the schedule. Not sample data."""
    questions = {q["id"]: q["question"] for q in raw["questions"]}
    items = {
        i["id"]: strip_emoji(i["name"]) for c in raw["categories"] if c["title"] == TRACK_CATEGORY for i in c["items"]
    }
    track_of = {str(s["id"]): [items[c] for c in s.get("categoryItems") or [] if c in items] for s in raw["sessions"]}
    out = []
    for s in raw["speakers"]:
        tracks = sorted({t for sid in s.get("sessions") or [] for t in track_of.get(str(sid), [])})
        out.append(
            {
                "id": s["id"],
                "kind": "speaker",
                "sample": False,
                "name": s["fullName"],
                "title": (s.get("tagLine") or "").split(",", 1)[-1].strip(),
                "company": speaker_company(s, questions),
                "bio": s.get("bio") or "",
                "interests": tracks,
                "interests_text": ", ".join(tracks),
                "session_ids": [str(x) for x in s.get("sessions") or []],
                "picture": s.get("profilePicture"),
            }
        )
    return out
