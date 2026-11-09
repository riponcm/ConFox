# Task: `next_food()` helper

**Owner:** [@yuzimeng2000-coder](https://github.com/yuzimeng2000-coder) · **Branch:** `feat/next-food` · **Area:** backend only (pure Python) · **Size:** about 30–50 lines plus tests

## Context: what Confox is

Confox is a conference guide for KubeCon + CloudNativeCon North America 2026 (Salt Lake City, 9–12 November 2026), built live at the WeMakeDevs Cloud Native Hackathon. It helps an attendee find the right talk, meet the right people and catch up on what they missed. Stack: FastAPI and Elasticsearch on the backend (Python 3.12+, managed with `uv`), React on the frontend, telemetry to Dash0. See [docs/idea.md](../idea.md) and [docs/architecture.md](../architecture.md#data-pull-request-2).

The demo user is **Emma** on Monday 9 November at 8:40 AM. The **Now** page (PR 5) will show "Next coffee in 8 min, Level 4 | Regency Ballroom B-D". This task is the logic behind that line.

## What to build

A pure function, no Elasticsearch and no FastAPI, that picks the food break that matters right now from a list of sessions.

### Files

| File | Action |
|---|---|
| `backend/app/now.py` | Create. Contains `next_food()` and nothing that talks to Elasticsearch. |
| `backend/tests/test_now.py` | Create. Tests with small hand-written session dicts. |

Do not change any other file.

### The data

Sessions are plain dicts, exactly as stored in the `confox-sessions` index (see `backend/app/data/sessions.py`). The fields you need:

```python
{
    "id": "1304201",
    "title": "Coffee Break",
    "starts_at": "2026-11-09T10:48:00",  # local conference time, no offset
    "ends_at": "2026-11-09T11:03:00",
    "day": "2026-11-09",
    "kind": "break",
    "is_food": True,                     # coffee, lunch, breakfast, receptions
    "room": "Hyatt Regency | Level 4 | Regency Ballroom B-D",
}
```

### The function

```python
from datetime import datetime

def next_food(sessions: list[dict], now: datetime) -> dict | None:
    """The food break that is on now, or else the next one today. None when there is none."""
```

`now` is a naive `datetime` in the same local time as the sessions (for example `datetime(2026, 11, 9, 8, 40)`). Parse session times with `datetime.fromisoformat`.

Return value:

```python
{
    "session": <the session dict>,
    "status": "now" | "next",
    "minutes": int,   # "now": minutes left until it ends; "next": minutes until it starts (rounded down)
}
```

Rules:

1. Only sessions with `is_food` true count.
2. If one is on now (`starts_at <= now < ends_at`), return it with `status: "now"`. If several are on, pick the one ending last.
3. Otherwise return the earliest one that starts after `now` **on the same day** (`day == now.date().isoformat()`), with `status: "next"`. If two start at the same time, pick the first by `id` so the result is stable.
4. Otherwise return `None` (no more food today; the page will say so).
5. Never raise on a session missing `starts_at` or `ends_at`; skip it.

### Tests to write (at least these)

| Case | Expect |
|---|---|
| Monday 8:40 with coffee at 10:48 and lunch at 12:46 | coffee, `"next"`, `128` minutes |
| Monday 10:55, during the 10:48–11:03 coffee | coffee, `"now"`, `8` minutes |
| Monday 18:00, after the last break | `None` |
| A food break tomorrow but none left today | `None` |
| A non-food session (`is_food` false) that starts sooner | ignored |
| A session with no `starts_at` | skipped, no error |

## Rules (from `.gitar/review/confox.md`)

- No emoji in code or tests. If you need a symbol in a test string, write it as an escape (`"☕ Coffee Break"`).
- Keep it pure: no Elasticsearch client, no environment variables, no network, so it is fast and testable.
- Type hints and a short docstring; ruff must pass (line length 120).

## Done when

- [ ] `cd backend && uv sync && uv run ruff check . && uv run ruff format --check . && uv run pytest -q` passes.
- [ ] Only the two files above changed.
- [ ] You can explain each rule and why `now` is naive (the schedule has no time zone offset; everyone reads it in Salt Lake City time).

## Open the pull request

```bash
git checkout -b feat/next-food
# build, then:
git add backend/app/now.py backend/tests/test_now.py
git commit -m "Add next_food() helper for the Now page"
git push -u origin feat/next-food
gh pr create --base main --title "next_food() helper for the Now page" --body "Implements docs/tasks/next-food.md."
```
