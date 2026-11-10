"""Dashboard: the conference pulse for one day, built entirely from Elasticsearch aggregations.

One `msearch` per request with four `size: 0` bodies: sessions (week, day timeline, tracks), people (who is here and
what attendees bring), agenda (what fills up next, and the signed-in user's own day) and activity (what people do in
Confox). "Filling up next" and "my day" read their few documents through `top_hits`, so no document search is needed.
Next coffee and what is on now stay on `GET /api/now`.

`GET /api/dashboard?day=YYYY-MM-DD&user_id=...` (defaults: the day of `clock.now()`, `settings.demo_user`) returns:

    {
      "day": "2026-11-09",
      "now": "2026-11-09T08:40:00",          # clock.now(); the UI draws the now line from it
      "is_today": true,                      # whether `now` falls on `day`
      "days": [{"day": "2026-11-08", "sessions": 41}, ...],           # every day with sessions, in order (the week)
      "sessions": {"total": 600, "day": 78},
      "timeline": {
        "interval_minutes": 30,
        "buckets": [{"start": "2026-11-09T07:00:00", "total": 2, "mine": 0,
                     "kinds": {"talks": 2, "keynotes": 0, "colocated": 0, "food": 0, "other": 0}}, ...],
                                             # mine: user's confirmed items; kinds sum to total
        "kind_totals": {"talks": 50, "keynotes": 0, "colocated": 23, "food": 3, "other": 2}   # the day
      },
      "tracks": [{"name": "Project Lightning Talks", "sessions": 51}, ...],          # top 6 on the day
      "filling": [{"id": "1289760", "title": "...", "starts_at": "...", "room": "...", "going": 5}],
                                             # top 5 sessions starting after now on the day, by agenda items
      "my_day": {                            # the signed-in user's agenda on the day (sample data)
        "hours": 8.5, "goal_hours": 8,       # hours covered by confirmed items (overlaps counted once)
        "sessions": 1, "meetings": 1,        # confirmed items
        "requests": 1                        # pending meeting requests someone sent the user
      },
      "people": {
        "total": 792, "speakers": 712, "attendees": 80, "sample": 80,
        "countries": [{"name": "United States", "count": 35}, ...],     # attendees, top 6
        "schools": [{"name": "University of Utah", "count": 8, "pinned": true}, ...],  # attendees, host first
        "companies": [{"name": "Redwood Labs", "count": 15}, ...],      # attendees, top 6
        "interests": [{"name": "Multi-cluster", "count": 33}, ...]      # attendees, top 6
      },
      "activity": {                          # events in Confox on the day (includes sample events)
        "total": 160, "sample": 160,
        "kinds": [{"kind": "search", "count": 62}, ...],
        "buckets": [{"start": "2026-11-09T07:00:00", "count": 0}, ...],   # 30 minutes; on today, up to now
        "searches": [{"name": "platform engineering", "count": 10}, ...]   # top searches all week
      }
    }

Buckets cover 07:00 to 19:00 local time (24 half hours, empty ones included). Times are stored as local conference
time without an offset, so Elasticsearch's UTC buckets line up with the local clock.
"""

import logging
from datetime import date, datetime, timedelta

from elasticsearch import ApiError, TransportError
from fastapi import APIRouter, HTTPException
from opentelemetry import trace

from ..clock import now as clock_now
from ..config import settings
from ..es import es

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

INTERVAL_MINUTES = 30
DAY_START = "07:00:00"
DAY_END = "19:00:00"
TOP = 6
FILLING_SIZE = 5
GOAL_HOURS = 8
MY_ITEMS = 50
# Salt Lake City hosts: the local university leads the alumni list (review rule), the rest follow by count.
HOST_SCHOOL = "University of Utah"

# Session kinds folded into the five groups the timeline chart stacks, in stacking order. Food (`is_food` or a
# break) wins over the kind; anything not listed (registration, ...) is "other".
KIND_GROUPS = ("talks", "keynotes", "colocated", "food", "other")
TALK_KINDS = {"talk", "lightning", "tutorial", "contribfest", "poster", "showcase"}

TS_FORMAT = "%Y-%m-%dT%H:%M:%S"


class SearchFailed(Exception):
    """One body inside the msearch failed; `error` is Elasticsearch's error object for it."""

    def __init__(self, error: dict):
        super().__init__(f"dashboard search failed: {error}")
        self.error = error


def _ts(dt: datetime) -> str:
    return dt.strftime(TS_FORMAT)


def _day_bounds(day: str) -> tuple[str, str]:
    start = datetime.fromisoformat(f"{day}T00:00:00")
    return _ts(start), _ts(start + timedelta(days=1))


def _histogram(field: str, day: str) -> dict:
    return {
        "date_histogram": {
            "field": field,
            "fixed_interval": f"{INTERVAL_MINUTES}m",
            "min_doc_count": 0,
            "extended_bounds": {
                "min": f"{day}T{DAY_START}",
                "max": _ts(datetime.fromisoformat(f"{day}T{DAY_END}") - timedelta(minutes=1)),
            },
            "hard_bounds": {"min": f"{day}T{DAY_START}", "max": f"{day}T{DAY_END}"},
        }
    }


FOOD_FILTER = {"filter": {"term": {"is_food": True}}}


def sessions_body(day: str) -> dict:
    """Sessions: the week by day, then the day's timeline and tracks under a filter."""
    return {
        "size": 0,
        "track_total_hits": True,
        "aggs": {
            "days": {"terms": {"field": "day", "size": 31, "order": {"_key": "asc"}}},
            "day": {
                "filter": {"term": {"day": day}},
                "aggs": {
                    "tracks": {"terms": {"field": "track", "size": TOP}},
                    "timeline": {
                        **_histogram("starts_at", day),
                        "aggs": {"kinds": {"terms": {"field": "kind", "size": 30}, "aggs": {"food": FOOD_FILTER}}},
                    },
                },
            },
        },
    }


def _terms(field: str, size: int = TOP) -> dict:
    return {"terms": {"field": field, "size": size, "exclude": [""]}}


def people_body() -> dict:
    """People: everyone by kind, the sample count, and what attendees bring (countries, schools, employers)."""
    return {
        "size": 0,
        "track_total_hits": True,
        "aggs": {
            "kinds": {"terms": {"field": "kind", "size": 10}},
            "sample": {"filter": {"term": {"sample": True}}},
            "attendees": {
                "filter": {"term": {"kind": "attendee"}},
                "aggs": {
                    "countries": _terms("country"),
                    "schools": _terms("schools", TOP + 1),
                    "host_school": {"filter": {"term": {"schools": HOST_SCHOOL}}},
                    "companies": _terms("company"),
                    "interests": _terms("interests"),
                },
            },
        },
    }


def agenda_body(day: str, now: datetime, user_id: str) -> dict:
    """Agenda: the most-added sessions still to start on the day, and the user's own items on the day."""
    day_from, day_to = _day_bounds(day)
    after = max(_ts(now), _ts(datetime.fromisoformat(day_from) - timedelta(seconds=1)))
    return {
        "size": 0,
        "aggs": {
            "filling": {
                "filter": {
                    "bool": {
                        "filter": [
                            {"term": {"kind": "session"}},
                            {"term": {"status": "confirmed"}},
                            {"range": {"starts_at": {"gt": after, "lt": day_to}}},
                        ]
                    }
                },
                "aggs": {
                    "sessions": {
                        "terms": {
                            "field": "session_id",
                            "size": FILLING_SIZE,
                            "order": [{"_count": "desc"}, {"start": "asc"}],
                        },
                        "aggs": {
                            "start": {"min": {"field": "starts_at"}},
                            "doc": {"top_hits": {"size": 1, "_source": ["title", "starts_at", "room"]}},
                        },
                    }
                },
            },
            "mine": {
                "filter": {
                    "bool": {
                        "filter": [
                            {"term": {"user_id": user_id}},
                            {"range": {"starts_at": {"gte": day_from, "lt": day_to}}},
                        ]
                    }
                },
                "aggs": {
                    "items": {
                        "top_hits": {
                            "size": MY_ITEMS,
                            "sort": [{"starts_at": "asc"}],
                            "_source": ["kind", "status", "direction", "starts_at", "ends_at"],
                        }
                    }
                },
            },
        },
    }


def activity_body(day: str) -> dict:
    """Activity: the day's events by kind and per half hour, and the top search phrases of the week."""
    day_from, day_to = _day_bounds(day)
    return {
        "size": 0,
        "aggs": {
            "day": {
                "filter": {"range": {"at": {"gte": day_from, "lt": day_to}}},
                "aggs": {
                    "kinds": {"terms": {"field": "kind", "size": 20}},
                    "sample": {"filter": {"term": {"sample": True}}},
                    "timeline": _histogram("at", day),
                },
            },
            "searches": {"filter": {"term": {"kind": "search"}}, "aggs": {"terms": _terms("detail")}},
        },
    }


def bodies(day: str, now: datetime, user_id: str) -> list[tuple[str, dict]]:
    """The four searches of one dashboard request, with the index each one runs on."""
    return [
        (settings.idx_sessions, sessions_body(day)),
        (settings.idx_people, people_body()),
        (settings.idx_agenda, agenda_body(day, now, user_id)),
        (settings.idx_activity, activity_body(day)),
    ]


def _names(agg: dict) -> list[dict]:
    return [{"name": b["key"], "count": b["doc_count"]} for b in agg["buckets"]]


def pin_school(buckets: list[dict], host_count: int, size: int = TOP) -> list[dict]:
    """The host university first (when any attendee studied there), then the rest by count."""
    rest = [{"name": b["key"], "count": b["doc_count"]} for b in buckets if b["key"] != HOST_SCHOOL]
    if not host_count:
        return rest[:size]
    return [{"name": HOST_SCHOOL, "count": host_count, "pinned": True}, *rest[: size - 1]]


def covered_hours(items: list[dict]) -> float:
    """Hours covered by the given items, overlaps counted once, rounded to a quarter hour."""
    spans = sorted(
        (datetime.fromisoformat(i["starts_at"]), datetime.fromisoformat(i["ends_at"]))
        for i in items
        if i.get("starts_at") and i.get("ends_at") and i["ends_at"] > i["starts_at"]
    )
    total = timedelta()
    cur_start = cur_end = None
    for start, end in spans:
        if cur_end is None or start > cur_end:
            if cur_end is not None:
                total += cur_end - cur_start
            cur_start, cur_end = start, end
        else:
            cur_end = max(cur_end, end)
    if cur_end is not None:
        total += cur_end - cur_start
    return round(total.total_seconds() / 3600 * 4) / 4


def my_day(items: list[dict]) -> dict:
    confirmed = [i for i in items if i.get("status") == "confirmed"]
    requests = [
        i
        for i in items
        if i.get("kind") == "meeting"
        and i.get("status") == "pending"
        and (i.get("direction") or "incoming") == "incoming"
    ]
    return {
        "hours": covered_hours(confirmed),
        "goal_hours": GOAL_HOURS,
        "sessions": sum(1 for i in confirmed if i.get("kind") == "session"),
        "meetings": sum(1 for i in confirmed if i.get("kind") == "meeting"),
        "requests": len(requests),
    }


def mine_per_bucket(starts: list[str], items: list[dict]) -> list[int]:
    """How many confirmed items start inside each half hour that begins at one of `starts`."""
    edges = [datetime.fromisoformat(s) for s in starts]
    width = timedelta(minutes=INTERVAL_MINUTES)
    counts = [0] * len(edges)
    for item in items:
        if item.get("status") != "confirmed" or not item.get("starts_at"):
            continue
        at = datetime.fromisoformat(item["starts_at"])
        for i, edge in enumerate(edges):
            if edge <= at < edge + width:
                counts[i] += 1
                break
    return counts


def kind_group(kind: str) -> str:
    """The chart group of a session kind that is not food."""
    if kind in TALK_KINDS:
        return "talks"
    if kind == "keynote":
        return "keynotes"
    if kind == "colocated":
        return "colocated"
    return "other"


def kinds_in_bucket(bucket: dict) -> dict[str, int]:
    """Counts per chart group for one histogram bucket (kinds terms, each with its `is_food` count)."""
    out = dict.fromkeys(KIND_GROUPS, 0)
    for k in bucket.get("kinds", {}).get("buckets", []):
        food = k["doc_count"] if k["key"] == "break" else k.get("food", {}).get("doc_count", 0)
        out["food"] += food
        out[kind_group(k["key"])] += k["doc_count"] - food
    return out


def shape_activity(day_agg: dict, searches: dict, now: datetime, is_today: bool) -> dict:
    buckets = [{"start": b["key_as_string"], "count": b["doc_count"]} for b in day_agg["timeline"]["buckets"]]
    if is_today:  # the future has no activity yet: stop at the half hour that holds now, not at a row of zeros
        buckets = [b for b in buckets if datetime.fromisoformat(b["start"]) <= now]
    return {
        "total": day_agg["doc_count"],
        "sample": day_agg["sample"]["doc_count"],
        "kinds": [{"kind": b["key"], "count": b["doc_count"]} for b in day_agg["kinds"]["buckets"]],
        "buckets": buckets,
        "searches": _names(searches["terms"]),
    }


def shape(day: str, now: datetime, sessions: dict, people: dict, agenda: dict, activity: dict) -> dict:
    """Turn the four aggregation responses into the dashboard payload."""
    s, p, a, act = sessions["aggregations"], people["aggregations"], agenda["aggregations"], activity["aggregations"]
    is_today = now.date().isoformat() == day
    mine = [h["_source"] for h in a["mine"]["items"]["hits"]["hits"]]
    histogram = s["day"]["timeline"]["buckets"]
    per_bucket = mine_per_bucket([b["key_as_string"] for b in histogram], mine)
    per_kind = [kinds_in_bucket(b) for b in histogram]
    kind_totals = {g: sum(k[g] for k in per_kind) for g in KIND_GROUPS}
    kinds = {b["key"]: b["doc_count"] for b in p["kinds"]["buckets"]}
    att = p["attendees"]
    filling = []
    for b in a["filling"]["sessions"]["buckets"]:
        hit = b["doc"]["hits"]["hits"][0]["_source"]
        filling.append(
            {
                "id": b["key"],
                "title": hit.get("title", ""),
                "starts_at": hit.get("starts_at"),
                "room": (hit.get("room") or "").strip(),
                "going": b["doc_count"],
            }
        )
    return {
        "day": day,
        "now": _ts(now),
        "is_today": is_today,
        "days": [{"day": b["key"], "sessions": b["doc_count"]} for b in s["days"]["buckets"]],
        "sessions": {"total": sessions["hits"]["total"]["value"], "day": s["day"]["doc_count"]},
        "timeline": {
            "interval_minutes": INTERVAL_MINUTES,
            "buckets": [
                {"start": b["key_as_string"], "total": b["doc_count"], "mine": n, "kinds": k}
                for b, n, k in zip(histogram, per_bucket, per_kind, strict=True)
            ],
            "kind_totals": kind_totals,
        },
        "tracks": [{"name": b["key"], "sessions": b["doc_count"]} for b in s["day"]["tracks"]["buckets"]],
        "filling": filling,
        "my_day": my_day(mine),
        "people": {
            "total": people["hits"]["total"]["value"],
            "speakers": kinds.get("speaker", 0),
            "attendees": kinds.get("attendee", 0),
            "sample": p["sample"]["doc_count"],
            "countries": _names(att["countries"]),
            "schools": pin_school(att["schools"]["buckets"], att["host_school"]["doc_count"]),
            "companies": _names(att["companies"]),
            "interests": _names(att["interests"]),
        },
        "activity": shape_activity(act["day"], act["searches"], now, is_today),
    }


def _msearch(requests: list[tuple[str, dict]]) -> list[dict]:
    searches = [part for index, body in requests for part in ({"index": index}, body)]
    responses = es.msearch(searches=searches)["responses"]
    for r in responses:
        if "error" in r:
            raise SearchFailed(r["error"])
    return responses


@router.get("")
def dashboard(day: date | None = None, user_id: str | None = None) -> dict:
    now = clock_now()
    day_str = (day or now.date()).isoformat()
    try:
        sessions, people, agenda, activity = _msearch(bodies(day_str, now, user_id or settings.demo_user))
    except (ApiError, TransportError, SearchFailed) as exc:
        log.error("dashboard aggregations failed for %s: %s", day_str, exc, exc_info=exc)
        trace.get_current_span().record_exception(exc)
        raise HTTPException(status_code=503, detail="Elasticsearch is not available") from exc
    return shape(day_str, now, sessions, people, agenda, activity)
