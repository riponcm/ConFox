# Dash0 dashboard

`confox-dashboard.json` is the "Confox overview" dashboard as code (Perses format).

Import: in Dash0 pick the dataset the app sends to (`confox`), open **Dashboards → Create → ⋮ → Edit as JSON**, paste the file, **Apply**, **Save**.

| Row | Panels | Source |
|---|---|---|
| Stats | Searches, match requests, Ask and Catch up turns, Claude cost (last hour); API error rate and p95 (last 5 minutes) | `confox.*` metrics; span metrics |
| Search | Search latency p95 by mode (bm25 vs hybrid); requests by route | `confox.search.duration`; `dash0.spans` |
| Claude | Tokens per minute (input, output); call p95 | `confox.llm.tokens`, `confox.llm.duration` |
| Health | Errors by service; Elasticsearch calls by operation | `dash0.spans` |

Queries use fixed 5-minute rate windows, which read better on low traffic than automatic ones. The Elasticsearch 9 client traces its calls as `INTERNAL` spans, so the Elasticsearch panel filters on that kind.
