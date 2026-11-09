"""Turn the raw Sessionize export into session documents.

The export groups tags into categories; the "All Sessions" category is the track. Kinds are derived from the
track and the title. Titles and track names can start with emoji ("☕ Coffee Break", "⚡ Lightning Talks"), so text
is normalised before matching.
"""

import re
import unicodedata
from datetime import datetime

TRACK_CATEGORY = "All Sessions"
LEVEL_CATEGORY = "Audience Level"
PROJECTS_CATEGORY = "CNCF Projects"

FOOD = re.compile(r"^(coffee|lunch|breakfast|snack|reception)\b", re.I)
BREAK = re.compile(r"^(coffee break|break)\b", re.I)

KIND_BY_TRACK = {
    "Registration": "registration",
    "Breaks": "break",
    "Keynote Sessions": "keynote",
    "CNCF-hosted Co-located Events": "colocated",
    "Sponsor-hosted Co-located Events": "colocated",
    "Lightning Talks": "lightning",
    "Project Lightning Talks": "lightning",
    "Tutorials": "tutorial",
    "Contribfest": "contribfest",
    "Poster Sessions": "poster",
    "Solutions Showcase": "showcase",
    "Cloud Native Theater": "showcase",
    "Sponsor Demo Theater": "showcase",
    "Project Pavilion Stage": "showcase",
    "Project Pavilion Tours": "showcase",
}


def strip_emoji(text: str) -> str:
    """Drop emoji and other symbols, then tidy whitespace: '☕ Coffee Break' -> 'Coffee Break'."""
    kept = "".join(ch for ch in text if unicodedata.category(ch) not in ("So", "Sk", "Cs", "Mn", "Cf"))
    return re.sub(r"\s+", " ", kept).strip()


def classify(track: str | None, title: str) -> tuple[str, bool]:
    """Return (kind, is_food) from the cleaned track and title."""
    clean = strip_emoji(title)
    if FOOD.match(clean) or BREAK.match(clean):
        return "break", bool(FOOD.match(clean))
    return KIND_BY_TRACK.get(track or "", "talk"), False


def _venue(room: str) -> str:
    return room.split("|")[0].strip() if room else ""


def build_sessions(raw: dict) -> list[dict]:
    items = {i["id"]: (c["title"], strip_emoji(i["name"])) for c in raw["categories"] for i in c["items"]}
    rooms = {r["id"]: r["name"] for r in raw["rooms"]}
    speakers = {s["id"]: s for s in raw["speakers"]}
    questions = {q["id"]: q["question"] for q in raw["questions"]}

    docs = []
    for s in raw["sessions"]:
        if not s.get("startsAt"):
            continue
        tags: dict[str, list[str]] = {}
        for cid in s.get("categoryItems") or []:
            group, name = items.get(cid, (None, None))
            if group:
                tags.setdefault(group, []).append(name)
        track = (tags.get(TRACK_CATEGORY) or [None])[0]
        title = strip_emoji(s["title"])
        kind, is_food = classify(track, s["title"])
        answers = {questions.get(a["questionId"]): a["answerValue"] for a in s.get("questionAnswers") or []}
        people = [speakers[i] for i in s.get("speakers") or [] if i in speakers]
        room = rooms.get(s.get("roomId"), "")
        start, end = datetime.fromisoformat(s["startsAt"]), datetime.fromisoformat(s["endsAt"])
        docs.append(
            {
                "id": s["id"],
                "title": title,
                "description": (s.get("description") or "").strip(),
                "starts_at": s["startsAt"],
                "ends_at": s["endsAt"],
                "day": s["startsAt"][:10],
                "minutes": int((end - start).total_seconds() // 60),
                "kind": kind,
                "is_food": is_food,
                "track": track,
                "level": (tags.get(LEVEL_CATEGORY) or [None])[0],
                "projects": tags.get(PROJECTS_CATEGORY, []),
                "room": room,
                "venue": _venue(room),
                "speaker_ids": [p["id"] for p in people],
                "speaker_names": [p["fullName"] for p in people],
                "companies": sorted({speaker_company(p, questions) for p in people} - {""}),
                "sponsored": "Is Sponsored Keynote" in tags,
                "end_user": "End User Programming" in tags,
                "slides_url": answers.get("Presentation Slides"),
            }
        )
    return docs


def speaker_company(speaker: dict, questions: dict[int, str]) -> str:
    """The speaker's company from their "Company" answer, or the part of the tag line before the comma."""
    for a in speaker.get("questionAnswers") or []:
        if questions.get(a["questionId"]) == "Company":
            return a["answerValue"].strip()
    return (speaker.get("tagLine") or "").split(",")[0].strip()
