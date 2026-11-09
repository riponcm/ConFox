"""Index mappings. Each index is created or rebuilt on its own, so reloading one never touches another."""

import logging

from .config import settings
from .es import es

log = logging.getLogger(__name__)

# Schedule times are local conference time (America/Denver) without an offset, as the source publishes them.
LOCAL_TIME = {"type": "date", "format": "strict_date_hour_minute_second"}
TEXT_KW = {"type": "text", "fields": {"raw": {"type": "keyword", "ignore_above": 512}}}
# Semantic search vector. Elasticsearch 9 keeps it out of `_source` unless a request asks for it.
EMBEDDING = {"type": "dense_vector", "dims": settings.embed_dims, "similarity": "cosine", "index": True}

MAPPINGS: dict[str, dict] = {
    settings.idx_sessions: {
        "properties": {
            "title": TEXT_KW,
            "description": {"type": "text"},
            "starts_at": LOCAL_TIME,
            "ends_at": LOCAL_TIME,
            "day": {"type": "keyword"},
            "minutes": {"type": "integer"},
            "kind": {"type": "keyword"},
            "is_food": {"type": "boolean"},
            "track": {"type": "keyword"},
            "level": {"type": "keyword"},
            "projects": {"type": "keyword"},
            "room": {"type": "keyword"},
            "venue": {"type": "keyword"},
            "speaker_ids": {"type": "keyword"},
            "speaker_names": TEXT_KW,
            "companies": {"type": "keyword"},
            "sponsored": {"type": "boolean"},
            "end_user": {"type": "boolean"},
            "slides_url": {"type": "keyword", "index": False},
            "embedding": EMBEDDING,
        }
    },
    settings.idx_people: {
        "properties": {
            "kind": {"type": "keyword"},
            "sample": {"type": "boolean"},
            "name": TEXT_KW,
            "title": {"type": "text"},
            "company": {"type": "keyword"},
            "bio": {"type": "text"},
            "interests": {"type": "keyword"},
            "interests_text": {"type": "text"},
            "schools": {"type": "keyword"},
            "past_companies": {"type": "keyword"},
            "communities": {"type": "keyword"},
            "city": {"type": "keyword"},
            "country": {"type": "keyword"},
            "session_ids": {"type": "keyword"},
            "picture": {"type": "keyword", "index": False},
            "embedding": EMBEDDING,
        }
    },
    settings.idx_agenda: {
        "properties": {
            "user_id": {"type": "keyword"},
            "kind": {"type": "keyword"},
            "status": {"type": "keyword"},
            "session_id": {"type": "keyword"},
            "with_id": {"type": "keyword"},
            "with_name": {"type": "keyword"},
            "title": {"type": "text"},
            "starts_at": LOCAL_TIME,
            "ends_at": LOCAL_TIME,
            "room": {"type": "keyword"},
            "sample": {"type": "boolean"},
        }
    },
}


def rebuild(index: str) -> None:
    """Drop and recreate exactly one index with its mapping."""
    if index not in MAPPINGS:
        raise ValueError(f"unknown index {index}")
    es.indices.delete(index=index, ignore_unavailable=True)
    # Single-node cluster in development: a replica could never be placed and would leave the cluster yellow.
    es.indices.create(index=index, mappings=MAPPINGS[index], settings={"number_of_replicas": 0})
    log.info("rebuilt index %s", index)
