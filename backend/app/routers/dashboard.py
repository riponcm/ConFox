"""Dashboard: the conference pulse for one day, built entirely from Elasticsearch aggregations.

Two `size: 0` searches per request: one on sessions (stats, timeline, tracks, kinds, next up) and one on people
(sample attendees, their countries, speaker companies). "Starting soon" is a `top_hits` aggregation, so no
document search is needed.

`GET /api/dashboard?day=YYYY-MM-DD` (default: the day of `clock.now()`) returns:

    {
      "day": "2026-11-09",
      "now": "2026-11-09T08:40:00",          # clock.now(); the UI draws the now line from it
      "is_today": true,                      # whether `now` falls on `day`
      "days": [{"day": "2026-11-09", "sessions": 78}, ...],          # every day with sessions, in order
      "stats": {
        "sessions_total": 600, "sessions_day": 78,
        "speakers_total": 712, "speakers_day": 120,                  # distinct speaker_ids
        "tracks_total": 40, "tracks_day": 5,                         # distinct tracks
        "sample_attendees": 80, "countries": 7                       # people with sample: true
      },
      "timeline": {
        "interval_minutes": 30,
        "groups": ["talks", "keynotes", "colocated", "breaks", "other"],
        "buckets": [{"start": "2026-11-09T07:00:00", "total": 2,
                     "counts": {"talks": 0, "keynotes": 0, "colocated": 0, "breaks": 0, "other": 2}}, ...]
      },
      "next_up": [{"id": "...", "title": "...", "starts_at": "...", "room": "...", "kind": "colocated"}],  # up to 6
      "next_up_total": 9,                    # sessions starting in the next 90 minutes, excluding registration
      "tracks": [{"name": "Project Lightning Talks", "sessions": 51}, ...],    # top 10 on the day
      "kinds": [{"kind": "lightning", "sessions": 48}, ...],                   # on the day
      "people": {
        "countries": [{"name": "United States", "attendees": 35}, ...],       # sample attendees
        "companies": [{"name": "Google", "speakers": 51}, ...]                # all speakers, top 10
      }
    }

Timeline buckets cover 07:00 to 19:00 local time (24 half hours, empty ones included). Times are stored as local
conference time without an offset, so Elasticsearch's UTC buckets line up with the local clock.
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
NEXT_UP_MINUTES = 90
NEXT_UP_SIZE = 6
TOP_TRACKS = 10
TOP_COMPANIES = 10
TOP_COUNTRIES = 20

# Kind groups for the timeline, in stacking order. Kinds not listed fall into "other".
GROUPS = ["talks", "keynotes", "colocated", "breaks", "other"]
GROUP_OF_KIND = {
    "talk": "talks",
    "lightning": "talks",
    "tutorial": "talks",
    "contribfest": "talks",
    "keynote": "keynotes",
    "colocated": "colocated",
    "break": "breaks",
}

TS_FORMAT = "%Y-%m-%dT%H:%M:%S"


def _ts(dt: datetime) -> str:
    return dt.strftime(TS_FORMAT)


def sessions_body(day: str, now: datetime) -> dict:
    """One size-0 search over all sessions: overall stats, then everything about `day` under a filter."""
    soon_from, soon_to = _ts(now), _ts(now + timedelta(minutes=NEXT_UP_MINUTES))
    return {
        "size": 0,
        "track_total_hits": True,
        "aggs": {
            "speakers": {"cardinality": {"field": "speaker_ids"}},
            "tracks": {"cardinality": {"field": "track"}},
            "days": {"terms": {"field": "day", "size": 31, "order": {"_key": "asc"}}},
            "day": {
                "filter": {"term": {"day": day}},
                "aggs": {
                    "speakers": {"cardinality": {"field": "speaker_ids"}},
                    "tracks_count": {"cardinality": {"field": "track"}},
                    "tracks": {"terms": {"field": "track", "size": TOP_TRACKS}},
                    "kinds": {"terms": {"field": "kind", "size": 20}},
                    "timeline": {
                        "date_histogram": {
                            "field": "starts_at",
                            "fixed_interval": f"{INTERVAL_MINUTES}m",
                            "min_doc_count": 0,
                            "extended_bounds": {
                                "min": f"{day}T{DAY_START}",
                                "max": _ts(datetime.fromisoformat(f"{day}T{DAY_END}") - timedelta(minutes=1)),
                            },
                            "hard_bounds": {"min": f"{day}T{DAY_START}", "max": f"{day}T{DAY_END}"},
                        },
                        "aggs": {"kinds": {"terms": {"field": "kind", "size": 20}}},
                    },
                    "next_up": {
                        "filter": {
                            "bool": {
                                "filter": [{"range": {"starts_at": {"gte": soon_from, "lte": soon_to}}}],
                                "must_not": [{"term": {"kind": "registration"}}],
                            }
                        },
                        "aggs": {
                            "hits": {
                                "top_hits": {
                                    "size": NEXT_UP_SIZE,
                                    "sort": [{"starts_at": "asc"}, {"title.raw": "asc"}],
                                    "_source": ["title", "starts_at", "room", "kind"],
                                }
                            }
                        },
                    },
                },
            },
        },
    }


def people_body() -> dict:
    """One size-0 search over people: sample attendees and their countries, companies of speakers."""
    return {
        "size": 0,
        "aggs": {
            "sample": {
                "filter": {"term": {"sample": True}},
                "aggs": {
                    "countries": {"terms": {"field": "country", "size": TOP_COUNTRIES}},
                    "countries_count": {"cardinality": {"field": "country"}},
                },
            },
            "speakers": {
                "filter": {"term": {"kind": "speaker"}},
                "aggs": {"companies": {"terms": {"field": "company", "size": TOP_COMPANIES, "exclude": [""]}}},
            },
        },
    }


def group_counts(kind_buckets: list[dict]) -> dict[str, int]:
    """Fold per-kind terms buckets into the timeline's kind groups."""
    counts = dict.fromkeys(GROUPS, 0)
    for b in kind_buckets:
        counts[GROUP_OF_KIND.get(b["key"], "other")] += b["doc_count"]
    return counts


def shape_timeline(histogram: dict) -> dict:
    buckets = [
        {
            "start": b["key_as_string"],
            "total": b["doc_count"],
            "counts": group_counts(b["kinds"]["buckets"]),
        }
        for b in histogram["buckets"]
    ]
    return {"interval_minutes": INTERVAL_MINUTES, "groups": GROUPS, "buckets": buckets}


def _terms(agg: dict, name: str, count: str) -> list[dict]:
    return [{name: b["key"], count: b["doc_count"]} for b in agg["buckets"]]


def shape(day: str, now: datetime, sessions: dict, people: dict) -> dict:
    """Turn the two aggregation responses into the dashboard payload."""
    s, p = sessions["aggregations"], people["aggregations"]
    d = s["day"]
    next_up = [
        {
            "id": h["_id"],
            "title": h["_source"].get("title", ""),
            "starts_at": h["_source"].get("starts_at"),
            "room": (h["_source"].get("room") or "").strip(),
            "kind": h["_source"].get("kind"),
        }
        for h in d["next_up"]["hits"]["hits"]["hits"]
    ]
    return {
        "day": day,
        "now": _ts(now),
        "is_today": now.date().isoformat() == day,
        "days": _terms(s["days"], "day", "sessions"),
        "stats": {
            "sessions_total": sessions["hits"]["total"]["value"],
            "sessions_day": d["doc_count"],
            "speakers_total": s["speakers"]["value"],
            "speakers_day": d["speakers"]["value"],
            "tracks_total": s["tracks"]["value"],
            "tracks_day": d["tracks_count"]["value"],
            "sample_attendees": p["sample"]["doc_count"],
            "countries": p["sample"]["countries_count"]["value"],
        },
        "timeline": shape_timeline(d["timeline"]),
        "next_up": next_up,
        "next_up_total": d["next_up"]["doc_count"],
        "tracks": _terms(d["tracks"], "name", "sessions"),
        "kinds": _terms(d["kinds"], "kind", "sessions"),
        "people": {
            "countries": _terms(p["sample"]["countries"], "name", "attendees"),
            "companies": _terms(p["speakers"]["companies"], "name", "speakers"),
        },
    }


@router.get("")
def dashboard(day: date | None = None) -> dict:
    now = clock_now()
    day_str = (day or now.date()).isoformat()
    try:
        sessions = es.search(index=settings.idx_sessions, **sessions_body(day_str, now))
        people = es.search(index=settings.idx_people, **people_body())
    except (ApiError, TransportError) as exc:
        log.error("dashboard aggregations failed for %s: %s", day_str, exc, exc_info=exc)
        trace.get_current_span().record_exception(exc)
        raise HTTPException(status_code=503, detail="Elasticsearch is not available") from exc
    return shape(day_str, now, sessions.body, people.body)
