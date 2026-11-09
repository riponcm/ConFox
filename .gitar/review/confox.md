# Confox review rules

Apply these on every pull request in addition to normal correctness review.

## Data
- Elasticsearch is the only data store. Flag any new database, file-based store or in-memory cache that holds user data across requests.
- Index names come from one config module; flag hard-coded index names elsewhere.
- Re-indexing one index must never delete or recreate another.
- Demo data lists University of Utah first wherever universities are seeded or ranked by default.

## Observability
- Every new API endpoint must be traced (auto-instrumented or an explicit span) and must not swallow exceptions silently.
- LLM calls must record model, token counts and cost.

## Security
- No secrets in the repository. `.env` stays git-ignored; `.env.example` holds names only.
- Nothing secret in `VITE_*` variables: they ship to the browser. Only the ingest-only Dash0 token may appear there.
- API keys (Anthropic, OpenAI, Dash0 auth) are read server side only.

## Frontend
- No emoji in UI text or code. Icons come from lucide-react only.
- One colour system: use the CSS variables in `src/index.css`; flag new hard-coded colours.
- Pages must work at phone width (375px) without horizontal scroll.

## Pull requests
- One feature per pull request. Flag unrelated changes bundled in.
- Generated or sample data must be labelled as such in the UI.
