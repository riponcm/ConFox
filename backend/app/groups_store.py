"""Meetup groups: people who share a school, country, company, community or interest meet at a food break.

One document per group in `confox-groups`:

    { title, basis: "school" | "country" | "company" | "community" | "interest", value ("University of Utah"),
      description, host_id, host_name, members [ids, host first], member_names (same order), max_members,
      proposed_slots [{session_id, title, starts_at, ends_at, room}]   (1 to 3 food or coffee breaks),
      votes {session_id: [user ids]}, fixed_slot (one of the proposed slots, or null), status: "open" | "fixed",
      created_at, sample }

Hallway board posts share the index with `type: "post"`:

    { type: "post", text (<= 140 chars), place, tags (from the author's interests), author_id, author_name,
      created_at, expires_at (30 minutes, 1 hour or 3 hours later), sample }

When the host fixes a time every member gets a confirmed agenda meeting "Meetup: <title>" with the id
"{user_id}-g-{group_id}", so joining or leaving a fixed group adds or removes exactly that one item.

The rules are pure functions, tested without Elasticsearch; they raise GroupError with the HTTP status to answer.
"""

import secrets
from datetime import datetime, timedelta

from elasticsearch import NotFoundError

from .agenda_store import meeting_title, stamp
from .clock import now
from .config import settings
from .es import es

BASES = ("school", "country", "company", "community", "interest")
# Ranking and suggestion order: alumni ties first (the demo's headline), then where people are from.
BASIS_ORDER = {b: i for i, b in enumerate(("school", "country", "community", "company", "interest"))}
MAX_SLOTS = 3
DEFAULT_MAX_MEMBERS = 12
MAX_MEMBERS_CAP = 50
TITLE_CHARS = 80
DESCRIPTION_CHARS = 280
MAX_SUGGESTIONS = 6

# How each basis reads in a match reason and in a suggestion.
MATCH_LABEL = {
    "school": "You studied at {v}",
    "country": "You are from {v}",
    "company": "You work or worked at {v}",
    "community": "You are in {v}",
    "interest": "You are into {v}",
}
SUGGEST_TITLE = {
    "school": "{v} alumni meetup",
    "country": "{v} meetup",
    "company": "{v} folks meetup",
    "community": "{v} meetup",
    "interest": "{v} meetup",
}


class GroupError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


# ---------- pure rules ----------


def _list(v) -> list[str]:
    if v is None or v == "":
        return []
    return [x for x in v if x] if isinstance(v, list) else [v]


def profile_values(user: dict) -> dict[str, list[str]]:
    """The user's own values per basis, in profile order. Company is the current one, then past ones."""
    return {
        "school": _list(user.get("schools")),
        "country": _list(user.get("country")),
        "company": list(dict.fromkeys(_list(user.get("company")) + _list(user.get("past_companies")))),
        "community": _list(user.get("communities")),
        "interest": _list(user.get("interests")),
    }


def group_id() -> str:
    return f"grp-{secrets.token_hex(4)}"


def agenda_item_id(user_id: str, gid: str) -> str:
    return f"{user_id}-g-{gid}"


def clean(text: str | None, limit: int) -> str:
    return " ".join((text or "").split())[:limit]


def slot_of(session: dict) -> dict:
    """A proposed slot from a food or coffee break session (with `id`)."""
    return {
        "session_id": session["id"],
        "title": meeting_title(session.get("title", "")),
        "starts_at": session["starts_at"],
        "ends_at": session["ends_at"],
        "room": session.get("room"),
    }


def new_group(
    gid: str,
    host: dict,
    basis: str,
    value: str,
    title: str,
    description: str,
    slots: list[dict],
    max_members: int = DEFAULT_MAX_MEMBERS,
    at: datetime | None = None,
    sample: bool = False,
) -> dict:
    """A new open group with the host as its first member. `host` needs `id` and `name`; `slots` are break sessions."""
    if basis not in BASES:
        raise GroupError(422, f"basis must be one of {', '.join(BASES)}")
    value = clean(value, TITLE_CHARS)
    if not value:
        raise GroupError(422, "value is required")
    ids = [s["id"] for s in slots]
    if not 1 <= len(ids) <= MAX_SLOTS or len(set(ids)) != len(ids):
        raise GroupError(422, f"pick 1 to {MAX_SLOTS} different times")
    proposed = sorted((slot_of(s) for s in slots), key=lambda s: (s["starts_at"], s["session_id"]))
    return {
        "id": gid,
        "type": "group",
        "title": clean(title, TITLE_CHARS) or SUGGEST_TITLE[basis].format(v=value),
        "basis": basis,
        "value": value,
        "description": clean(description, DESCRIPTION_CHARS),
        "host_id": host["id"],
        "host_name": host.get("name") or host["id"],
        "members": [host["id"]],
        "member_names": [host.get("name") or host["id"]],
        "max_members": max(2, min(int(max_members or DEFAULT_MAX_MEMBERS), MAX_MEMBERS_CAP)),
        "proposed_slots": proposed,
        "votes": {s["session_id"]: [] for s in proposed},
        "fixed_slot": None,
        "status": "open",
        "created_at": stamp(at),
        "sample": sample,
    }


def match_reason(group: dict, user: dict) -> dict | None:
    """Why this group is relevant to the user: the group's value is one of theirs for the same basis."""
    basis, value = group.get("basis"), group.get("value")
    if basis in BASIS_ORDER and value in profile_values(user)[basis]:
        return {"basis": basis, "value": value, "label": MATCH_LABEL[basis].format(v=value)}
    return None


def is_member(group: dict, user_id: str) -> bool:
    return user_id in (group.get("members") or [])


def tally(group: dict, user_id: str = "") -> list[dict]:
    """Proposed slots in time order, each with its vote count and whether `user_id` voted for it."""
    votes = group.get("votes") or {}
    out = []
    for s in sorted(group.get("proposed_slots") or [], key=lambda s: (s["starts_at"], s["session_id"])):
        voters = votes.get(s["session_id"]) or []
        out.append(s | {"votes": len(voters), "voted": user_id in voters})
    return out


def leading_slot(group: dict) -> str | None:
    """The slot with most votes (earliest on a tie), or None when nobody has voted."""
    ranked = sorted(tally(group), key=lambda s: (-s["votes"], s["starts_at"]))
    return ranked[0]["session_id"] if ranked and ranked[0]["votes"] else None


def view(group: dict, user_id: str, user: dict | None = None) -> dict:
    """The group as the API returns it to one user."""
    members = group.get("members") or []
    return group | {
        "member_count": len(members),
        "spots_left": max(0, (group.get("max_members") or DEFAULT_MAX_MEMBERS) - len(members)),
        "is_member": user_id in members,
        "is_host": group.get("host_id") == user_id,
        "match": match_reason(group, user) if user else None,
        "tally": tally(group, user_id),
        "leading": leading_slot(group),
    }


def _rank_key(group: dict, user: dict) -> tuple:
    reason = match_reason(group, user)
    return (
        reason is None,  # groups sharing one of the user's values first
        BASIS_ORDER[reason["basis"]] if reason else 0,
        group.get("status") != "open",  # still deciding before already fixed
        -len(group.get("members") or []),
        group.get("created_at") or "",
        group.get("id") or "",
    )


def rank(groups: list[dict], user_id: str, user: dict) -> dict:
    """{"groups": others ranked for the user, "mine": groups they host or joined, earliest fixed time first}."""
    mine = [g for g in groups if is_member(g, user_id)]
    others = [g for g in groups if not is_member(g, user_id)]
    others.sort(key=lambda g: _rank_key(g, user))
    mine.sort(key=lambda g: ((g.get("fixed_slot") or {}).get("starts_at") or "9", g.get("created_at") or ""))
    return {"groups": [view(g, user_id, user) for g in others], "mine": [view(g, user_id, user) for g in mine]}


def join(group: dict, user_id: str, name: str) -> dict:
    """The group with the user added. Joining twice is a no-op; a full group refuses (409)."""
    if is_member(group, user_id):
        return group
    members = group.get("members") or []
    if len(members) >= (group.get("max_members") or DEFAULT_MAX_MEMBERS):
        raise GroupError(409, "this group is full")
    return group | {"members": members + [user_id], "member_names": (group.get("member_names") or []) + [name]}


def leave(group: dict, user_id: str) -> dict:
    """The group without the user, their votes removed too. The host cannot leave their own group (409)."""
    if group.get("host_id") == user_id:
        raise GroupError(409, "the host cannot leave their own group")
    members = group.get("members") or []
    if user_id not in members:
        return group
    i = members.index(user_id)
    names = list(group.get("member_names") or [])
    votes = {sid: [u for u in voters if u != user_id] for sid, voters in (group.get("votes") or {}).items()}
    return group | {
        "members": members[:i] + members[i + 1 :],
        "member_names": names[:i] + names[i + 1 :],
        "votes": votes,
    }


def proposed(group: dict, session_id: str) -> dict:
    slot = next((s for s in group.get("proposed_slots") or [] if s["session_id"] == session_id), None)
    if slot is None:
        raise GroupError(422, f"{session_id} is not one of this group's proposed times")
    return slot


def vote(group: dict, user_id: str, session_id: str, on: bool = True) -> dict:
    """Mark (or unmark) one proposed time the member can make. Members may vote for several times."""
    if group.get("status") != "open":
        raise GroupError(409, "the time is already fixed")
    if not is_member(group, user_id):
        raise GroupError(403, "join the group to vote")
    proposed(group, session_id)
    votes = {sid: list(voters) for sid, voters in (group.get("votes") or {}).items()}
    voters = [u for u in votes.get(session_id, []) if u != user_id]
    votes[session_id] = voters + [user_id] if on else voters
    return group | {"votes": votes}


def fix(group: dict, user_id: str, session_id: str) -> dict:
    """The host fixes one of the proposed times; the group becomes `fixed` (once)."""
    if group.get("host_id") != user_id:
        raise GroupError(403, "only the host can fix the time")
    if group.get("status") != "open":
        raise GroupError(409, "the time is already fixed")
    return group | {"status": "fixed", "fixed_slot": proposed(group, session_id)}


def agenda_item(group: dict, user_id: str, at: datetime | None = None) -> dict:
    """The confirmed agenda meeting a member gets once the time is fixed."""
    slot = group["fixed_slot"]
    return {
        "id": agenda_item_id(user_id, group["id"]),
        "user_id": user_id,
        "kind": "meeting",
        "status": "confirmed",
        "group_id": group["id"],
        "with_id": group["id"],
        "with_name": group["title"],
        "session_id": slot["session_id"],
        "title": f"Meetup: {group['title']}",
        "starts_at": slot["starts_at"],
        "ends_at": slot["ends_at"],
        "room": slot.get("room"),
        "sample": bool(group.get("sample")) and user_id != settings.demo_user,
        "created_at": stamp(at),
    }


def suggest_aggs(user_id: str, user: dict) -> dict:
    """One filters aggregation per basis, a bucket per value of the user's; the user is excluded in the query."""
    fields = {"school": ["schools"], "country": ["country"], "community": ["communities"], "interest": ["interests"]}
    fields["company"] = ["company", "past_companies"]
    aggs = {}
    for basis, values in profile_values(user).items():
        if not values:
            continue
        buckets = {}
        for v in values:
            clauses = [{"term": {f: v}} for f in fields[basis]]
            buckets[v] = clauses[0] if len(clauses) == 1 else {"bool": {"should": clauses, "minimum_should_match": 1}}
        aggs[basis] = {"filters": {"filters": buckets}}
    return aggs


def suggestions(user: dict, aggs: dict, groups: list[dict], limit: int = MAX_SUGGESTIONS) -> list[dict]:
    """Values the user shares with others, most telling basis first, then by how many people share them.

    Each says how many open groups already exist for it, so the page can point at them instead of a duplicate.
    """
    out = []
    for basis, values in profile_values(user).items():
        buckets = aggs.get(basis, {}).get("buckets", {})
        for order, v in enumerate(values):
            count = buckets.get(v, {}).get("doc_count", 0)
            if not count:
                continue
            existing = [g["id"] for g in groups if g.get("basis") == basis and g.get("value") == v]
            out.append(
                {
                    "basis": basis,
                    "value": v,
                    "count": count,
                    "label": f"{v} · {count} {'person' if count == 1 else 'people'} here",
                    "title": SUGGEST_TITLE[basis].format(v=v),
                    "existing": existing,
                    "_order": (BASIS_ORDER[basis], -count, order),
                }
            )
    out.sort(key=lambda s: s.pop("_order"))
    return out[:limit]


# ---------- hallway board ----------

POST_CHARS = 140
PLACE_CHARS = 60
POST_MINUTES = (30, 60, 180)
MAX_TAGS = 3
BOARD_SIZE = 40


def post_id() -> str:
    return f"post-{secrets.token_hex(4)}"


def new_post(
    pid: str,
    author: dict,
    text: str,
    place: str = "",
    minutes: int = 60,
    tags: list[str] | None = None,
    at: datetime | None = None,
    sample: bool = False,
) -> dict:
    """A board post. Tags are kept only when they are the author's own interests (at most three)."""
    text = clean(text, POST_CHARS)
    if not text:
        raise GroupError(422, "write something to post")
    if minutes not in POST_MINUTES:
        raise GroupError(422, "a post lasts 30, 60 or 180 minutes")
    start = (at or now()).replace(microsecond=0)
    own = profile_values(author)["interest"]
    return {
        "id": pid,
        "type": "post",
        "text": text,
        "place": clean(place, PLACE_CHARS),
        "tags": [t for t in own if t in set(tags or [])][:MAX_TAGS],
        "author_id": author["id"],
        "author_name": author.get("name") or author["id"],
        "created_at": stamp(start),
        "expires_at": stamp(start + timedelta(minutes=minutes)),
        "sample": sample,
    }


def board(posts: list[dict], groups: list[dict], user_id: str, user: dict, at: datetime) -> list[dict]:
    """The hallway feed, newest first: live posts (each says if it matches the viewer's interests and if it is
    theirs) and meetup groups still to happen (open, or fixed and not yet over)."""
    at_iso = stamp(at)
    mine = {i.lower() for i in profile_values(user)["interest"]}
    items = []
    for p in posts:
        if (p.get("expires_at") or "") <= at_iso:
            continue
        matching = [t for t in p.get("tags") or [] if t.lower() in mine]
        items.append(
            p | {"kind": "post", "for_you": bool(matching), "matching": matching, "mine": p["author_id"] == user_id}
        )
    for g in groups:
        fixed = g.get("fixed_slot") or {}
        if g.get("status") == "fixed" and (fixed.get("ends_at") or "") <= at_iso:
            continue
        reason = match_reason(g, user)
        items.append(
            {
                "kind": "group",
                "id": g["id"],
                "title": g.get("title"),
                "basis": g.get("basis"),
                "value": g.get("value"),
                "status": g.get("status"),
                "fixed_slot": g.get("fixed_slot"),
                "member_count": len(g.get("members") or []),
                "author_name": g.get("host_name"),
                "created_at": g.get("created_at"),
                "for_you": reason is not None,
                "is_member": is_member(g, user_id),
                "sample": bool(g.get("sample")),
            }
        )
    items.sort(key=lambda i: (i.get("created_at") or "", i["id"]), reverse=True)
    return items[:BOARD_SIZE]


def remove_check(post: dict, user_id: str) -> None:
    if post.get("type") != "post":
        raise GroupError(404, "no such post")
    if post.get("author_id") != user_id:
        raise GroupError(403, "only the author can remove a post")


# ---------- Elasticsearch ----------


def get(gid: str, kind: str = "group") -> tuple[dict, dict]:
    """The group (or, with kind "post", the board post) and its concurrency token ({if_seq_no, if_primary_term});
    404 when missing or of the other kind."""
    try:
        doc = es.get(index=settings.idx_groups, id=gid)
    except NotFoundError as exc:
        raise GroupError(404, f"no {kind} {gid}") from exc
    if (doc["_source"].get("type") == "post") != (kind == "post"):
        raise GroupError(404, f"no {kind} {gid}")
    return doc["_source"] | {"id": doc["_id"]}, {"if_seq_no": doc["_seq_no"], "if_primary_term": doc["_primary_term"]}


def save(group: dict, token: dict | None = None) -> None:
    """Write the group; with a token only if nobody changed it since it was read (ConflictError otherwise)."""
    body = {k: v for k, v in group.items() if k != "id"}
    es.index(index=settings.idx_groups, id=group["id"], document=body, refresh="wait_for", **(token or {}))


def all_posts(size: int = 200) -> list[dict]:
    r = es.search(index=settings.idx_groups, query={"term": {"type": "post"}}, sort=[{"created_at": "desc"}], size=size)
    return [h["_source"] | {"id": h["_id"]} for h in r["hits"]["hits"]]


def all_groups(size: int = 200) -> list[dict]:
    """Every meetup group (hallway posts share the index and are left out)."""
    query = {"bool": {"must_not": [{"term": {"type": "post"}}]}}
    r = es.search(index=settings.idx_groups, query=query, sort=[{"created_at": "asc"}], size=size)
    return [h["_source"] | {"id": h["_id"]} for h in r["hits"]["hits"]]
