# How we work

- One feature = one branch = one pull request. Gitar reviews every PR; merge after review and green CI.
- Keep secrets in `.env` only.
- Run checks before pushing:
  - backend: `uv run ruff check . && uv run ruff format --check . && uv run pytest -q`
  - frontend: `npm run lint && npm run build`
