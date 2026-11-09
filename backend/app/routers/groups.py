"""Groups: meetups for people who share a school, country, company, community or interest.

Someone proposes a group with up to three food or coffee breaks they are free for, others join and vote for the
times they can make, and the host fixes one; every member then has a confirmed "Meetup: <title>" on their agenda.
The rules live in app/groups_store.py; this module reads and writes Elasticsearch around them.
"""

from collections.abc import Callable

from elasticsearch import ConflictError, NotFoundError
from fastapi import APIRouter, HTTPException, Query
from opentelemetry import metrics, trace
from pydantic import BaseModel, Field

from .. import activity
from .. import agenda_store as agenda
from .. import groups_store as store
from ..clock import now
from ..config import settings
from ..es import es
from .connect import _food_sessions

router = APIRouter(prefix="/api/groups", tags=["groups"])
changes = metrics.get_meter("confox.groups").create_counter(
    "confox.groups.changes", unit="{change}", description="Meetup groups proposed, joined, left, voted on and fixed"
)
PROPOSE_SLOTS = 6  # free breaks offered when proposing; the host picks up to store.MAX_SLOTS of them


def _user_id() -> str:
    return Query(default_factory=lambda: settings.demo_user, min_length=1)


class Propose(BaseModel):
    user_id: str = Field(default_factory=lambda: settings.demo_user, min_length=1)
    basis: str
    value: str = Field(min_length=1, max_length=200)
    title: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=1000)
    session_ids: list[str] = Field(min_length=1, max_length=store.MAX_SLOTS)
    max_members: int = store.DEFAULT_MAX_MEMBERS


class SlotChoice(BaseModel):
    user_id: str = Field(default_factory=lambda: settings.demo_user, min_length=1)
    session_id: str = Field(min_length=1)
    vote: bool = True  # false takes the vote back


def _http(exc: store.GroupError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=exc.detail)


def _profile(user_id: str) -> dict:
    try:
        doc = es.get(index=settings.idx_people, id=user_id, source_excludes=["embedding", "bio"])
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"unknown user {user_id}") from exc
    return doc["_source"] | {"id": doc["_id"]}


def _free_breaks(user_id: str, limit: int = PROPOSE_SLOTS) -> list[dict]:
    """Food and coffee breaks the user is free for (today, then the next day with breaks), same rules as Meet."""
    items = agenda.user_items(user_id)
    kinds = agenda.session_kinds([i.get("session_id") or "" for i in items])
    return agenda.free_slots(_food_sessions(), items, kinds, "", now(), limit=limit)


def _write_agenda(group: dict, user_ids: list[str]) -> None:
    for uid in user_ids:
        item = store.agenda_item(group, uid)
        es.index(index=settings.idx_agenda, id=item.pop("id"), document=item)
    agenda.refresh()


def _busy_at(user_id: str, slot: dict | None, group_id: str) -> dict | None:
    """The user's confirmed item that overlaps the meetup slot (co-located days aside), other than this meetup."""
    if not slot:
        return None
    items = [i for i in agenda.user_items(user_id) if i.get("id") != store.agenda_item_id(user_id, group_id)]
    kinds = agenda.session_kinds([i.get("session_id") or "" for i in items])
    return next(
        (
            i
            for i in agenda.blocking(items, kinds)
            if agenda.overlaps(slot["starts_at"], slot["ends_at"], i["starts_at"], i["ends_at"])
        ),
        None,
    )


def _drop_agenda(group_id: str, user_id: str) -> None:
    try:
        es.delete(index=settings.idx_agenda, id=store.agenda_item_id(user_id, group_id))
    except NotFoundError:
        return
    agenda.refresh()


def _change(group_id: str, user_id: str, action: str, rule: Callable[[dict], dict]) -> tuple[dict, dict]:
    """Read the group, apply a pure rule, write it back only if nobody changed it meanwhile. Returns (before, after)."""
    span = trace.get_current_span()
    span.set_attribute("confox.groups.id", group_id)
    span.set_attribute("confox.groups.action", action)
    try:
        before, token = store.get(group_id)
        after = rule(before)
        if after is not before:
            store.save(after, token)
    except store.GroupError as exc:
        raise _http(exc) from exc
    except ConflictError as exc:
        # Two people joined or voted at the same moment; the page reloads and the user tries again.
        span.record_exception(exc)
        raise HTTPException(status_code=409, detail="the group just changed, try again") from exc
    changes.add(1, {"action": action})
    return before, after


@router.get("")
def groups(user_id: str = _user_id()) -> dict:
    """{"groups": groups the user is not in, ranked (sharing one of their values first, each with `match`),
    "mine": groups they host or joined}. Every group carries member_count, spots_left, tally and leading."""
    user = _profile(user_id)
    out = store.rank(store.all_groups(), user_id, user)
    trace.get_current_span().set_attribute("confox.groups.count", len(out["groups"]) + len(out["mine"]))
    return out


@router.get("/suggest")
def suggest(user_id: str = _user_id()) -> dict:
    """Groups worth proposing: values the user shares with others and how many people share each,
    e.g. {"basis": "school", "value": "University of Utah", "count": 8, "label": "University of Utah · 8 people here"}.
    """
    user = _profile(user_id)
    aggs = store.suggest_aggs(user_id, user)
    if not aggs:
        return {"suggestions": []}
    r = es.search(
        index=settings.idx_people, size=0, query={"bool": {"must_not": [{"ids": {"values": [user_id]}}]}}, aggs=aggs
    )
    open_groups = [g for g in store.all_groups() if g.get("status") == "open"]
    found = store.suggestions(user, r.get("aggregations", {}), open_groups)
    trace.get_current_span().set_attribute("confox.groups.suggestions", len(found))
    return {"suggestions": found}


@router.get("/slots")
def slots(user_id: str = _user_id()) -> dict:
    """Breaks the user is free for, to choose a group's candidate times from: {"slots": [...]}, at most 6."""
    found = _free_breaks(user_id)
    trace.get_current_span().set_attribute("confox.groups.slots", len(found))
    return {"slots": found}


@router.post("")
def propose(body: Propose) -> dict:
    """Create an open group hosted by the user. Every chosen time must be a break the host is free for (422)."""
    host = _profile(body.user_id)
    free = {s["session_id"] for s in _free_breaks(body.user_id, limit=50)}
    if missing := [sid for sid in body.session_ids if sid not in free]:
        raise HTTPException(status_code=422, detail=f"not a free break for you: {', '.join(missing)}")
    sessions = [agenda.get_session(sid) for sid in dict.fromkeys(body.session_ids)]
    try:
        group = store.new_group(
            store.group_id(),
            host,
            body.basis,
            body.value,
            body.title,
            body.description,
            [s for s in sessions if s],
            body.max_members,
        )
    except store.GroupError as exc:
        raise _http(exc) from exc
    store.save(group)
    trace.get_current_span().set_attribute("confox.groups.id", group["id"])
    changes.add(1, {"action": "propose"})
    activity.record("group_propose", body.user_id, f"{group['basis']} {group['value']}")
    return store.view(group, body.user_id, host)


@router.post("/{group_id}/join")
def join(group_id: str, user_id: str = _user_id()) -> dict:
    """Join a group (idempotent). If its time is already fixed, the meetup goes straight onto the user's agenda."""
    user = _profile(user_id)
    try:
        current, _ = store.get(group_id)
    except store.GroupError as exc:
        raise _http(exc) from exc
    if current.get("status") == "fixed" and not store.is_member(current, user_id):
        busy = _busy_at(user_id, current.get("fixed_slot"), group_id)
        if busy:  # joining would put a second confirmed item at the same time
            raise HTTPException(status_code=409, detail=f"you already have {busy.get('title') or 'something'} then")
    before, after = _change(group_id, user_id, "join", lambda g: store.join(g, user_id, user.get("name") or user_id))
    if after is not before:
        activity.record("group_join", user_id, group_id)
        if after.get("status") == "fixed":
            _write_agenda(after, [user_id])
    return store.view(after, user_id, user)


@router.post("/{group_id}/leave")
def leave(group_id: str, user_id: str = _user_id()) -> dict:
    """Leave a group and take back the user's votes; a fixed meetup leaves their agenda. The host cannot leave."""
    user = _profile(user_id)
    try:
        store.get(group_id)
    except store.GroupError as exc:
        if exc.status != 404:
            raise _http(exc) from exc
        # The group is gone (for example after a reload of the groups seed): clear its meetup off the agenda.
        _drop_agenda(group_id, user_id)
        return {"id": group_id, "removed": True}
    before, after = _change(group_id, user_id, "leave", lambda g: store.leave(g, user_id))
    if after is not before and after.get("status") == "fixed":
        _drop_agenda(group_id, user_id)
    return store.view(after, user_id, user)


@router.post("/{group_id}/vote")
def vote(group_id: str, body: SlotChoice) -> dict:
    """Vote for (or, with vote false, un-vote) one proposed time. Voting on a group joins it first."""
    user = _profile(body.user_id)
    name = user.get("name") or body.user_id

    def rule(g: dict) -> dict:
        return store.vote(store.join(g, body.user_id, name), body.user_id, body.session_id, body.vote)

    before, after = _change(group_id, body.user_id, "vote", rule)
    if not store.is_member(before, body.user_id):
        activity.record("group_join", body.user_id, group_id)
    if body.vote:
        activity.record("group_vote", body.user_id, group_id)
    return store.view(after, body.user_id, user)


@router.post("/{group_id}/fix")
def fix(group_id: str, body: SlotChoice) -> dict:
    """The host fixes one proposed time: the group becomes `fixed` and each member gets a confirmed agenda meeting."""
    user = _profile(body.user_id)
    _, after = _change(group_id, body.user_id, "fix", lambda g: store.fix(g, body.user_id, body.session_id))
    members = after.get("members") or []
    # Never double-book: members already busy at that time do not get the meetup on their agenda.
    busy = [m for m in members if _busy_at(m, after.get("fixed_slot"), group_id)]
    _write_agenda(after, [m for m in members if m not in busy])
    activity.record("group_fix", body.user_id, group_id)
    names = dict(zip(members, after.get("member_names") or [], strict=False))
    return store.view(after, body.user_id, user) | {"busy_members": [names.get(m, m) for m in busy]}


# ---------- hallway board ----------


class NewPost(BaseModel):
    user_id: str = Field(default_factory=lambda: settings.demo_user, min_length=1)
    text: str = Field(min_length=1, max_length=400)
    place: str = Field(default="", max_length=200)
    minutes: int = 60
    tags: list[str] = Field(default_factory=list, max_length=10)


@router.get("/board")
def board(user_id: str = _user_id()) -> dict:
    """The hallway board: {"items": live posts and upcoming meetup groups, newest first, each with `for_you`
    when it matches the viewer's interests (posts) or values (groups)}, plus the viewer's `interests` to tag with."""
    user = _profile(user_id)
    items = store.board(store.all_posts(), store.all_groups(), user_id, user, now())
    trace.get_current_span().set_attribute("confox.board.items", len(items))
    return {"items": items, "interests": store.profile_values(user)["interest"], "minutes": store.POST_MINUTES}


@router.post("/board")
def post(body: NewPost) -> dict:
    """Post a short line to the board for 30, 60 or 180 minutes. Tags not among the author's interests are dropped."""
    author = _profile(body.user_id)
    try:
        item = store.new_post(store.post_id(), author, body.text, body.place, body.minutes, body.tags)
    except store.GroupError as exc:
        raise _http(exc) from exc
    store.save(item)
    changes.add(1, {"action": "post"})
    activity.record("board_post", body.user_id, " ".join(item["tags"]))
    return item | {"kind": "post", "for_you": bool(item["tags"]), "matching": item["tags"], "mine": True}


@router.delete("/board/{post_id}")
def remove(post_id: str, user_id: str = _user_id()) -> dict:
    """The author takes their post down (403 for anyone else, 404 if it is not a post)."""
    trace.get_current_span().set_attribute("confox.board.post_id", post_id)
    try:
        item, token = store.get(post_id, kind="post")
        store.remove_check(item, user_id)
    except store.GroupError as exc:
        raise _http(exc) from exc
    es.delete(index=settings.idx_groups, id=post_id, refresh="wait_for", **token)
    changes.add(1, {"action": "unpost"})
    return {"id": post_id, "deleted": True}
