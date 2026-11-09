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
            # Speakers' published links, shown in session details; stored, never searched.
            "links": {"type": "object", "enabled": False},
            "embedding": EMBEDDING,
        }
    },
    settings.idx_activity: {
        "properties": {
            "at": LOCAL_TIME,
            "user_id": {"type": "keyword"},
            "kind": {"type": "keyword"},
            "detail": {"type": "keyword", "ignore_above": 120},
            "sample": {"type": "boolean"},
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
            # Meet: who asked (meetings only; a pending meeting without it is incoming), the note sent with it.
            "direction": {"type": "keyword"},
            "message": {"type": "text"},
            "request_id": {"type": "keyword"},
            "created_at": LOCAL_TIME,
            # Groups: the meetup group a confirmed "Meetup: ..." item belongs to.
            "group_id": {"type": "keyword"},
        }
    },
    # Meetup groups (app/groups_store.py). Slots and votes are kept as stored objects, not indexed: they are only
    # ever read back with their group, and break ids as field names would grow the mapping with every break.
    settings.idx_groups: {
        "properties": {
            "type": {"type": "keyword"},  # "group", or "post" for a hallway board post
            "title": TEXT_KW,
            "basis": {"type": "keyword"},
            "value": {"type": "keyword"},
            "description": {"type": "text"},
            "host_id": {"type": "keyword"},
            "host_name": {"type": "keyword"},
            "members": {"type": "keyword"},
            "member_names": {"type": "keyword"},
            "max_members": {"type": "integer"},
            "proposed_slots": {"type": "object", "enabled": False},
            "votes": {"type": "object", "enabled": False},
            "fixed_slot": {"type": "object", "enabled": False},
            "status": {"type": "keyword"},
            "created_at": LOCAL_TIME,
            "sample": {"type": "boolean"},
            # Hallway board posts (type "post"): short-lived lines like "At the Cilium booth till 15:00".
            "text": {"type": "text"},
            "place": {"type": "keyword"},
            "tags": {"type": "keyword"},
            "expires_at": LOCAL_TIME,
            "author_id": {"type": "keyword"},
            "author_name": {"type": "keyword"},
        }
    },
    # Sample keynote transcripts in ~200-word chunks (doc_type "chunk"), plus one cached Claude summary per talk
    # (doc_type "summary", id "summary-<session_id>"). Rebuilding this index only clears the cached summaries.
    settings.idx_transcripts: {
        "properties": {
            "doc_type": {"type": "keyword"},
            "session_id": {"type": "keyword"},
            "chunk": {"type": "integer"},
            "text": {"type": "text"},
            "sample": {"type": "boolean"},
            "tldr": {"type": "text"},
            "takeaways": {"type": "text"},
            "model": {"type": "keyword"},
            "created_at": LOCAL_TIME,
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
