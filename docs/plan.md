# Plan

One feature = one branch = one pull request. Gitar reviews every pull request; it merges after review and green CI.

## Parallel lanes

Work is split so pull requests rarely touch the same files.

| Lane | Owns | Pull requests |
|---|---|---|
| A · Platform | repo, compose, CI, review rules, telemetry, data loading | 0, 1, 2, 12 |
| B · Search & data | search, schedule, dashboard, agenda | 3, 4, 5, 11 |
| C · People | profiles, match, connect | 6, 7 |
| D · AI | Ask, Catch up, brief | 8, 9, 10 |
| E · Frontend shell | layout, nav, theme, shared components | 2b |

## Build order

| # | Pull request | Priority | Simple version | Done when |
|---|---|---|---|---|
| 0 | Repo, compose, CI, review rules | Must | Health endpoint, one test, CI for both halves | Gitar reviews it; CI runs |
| 1 | Telemetry | Must | API traces, logs, LLM spans; browser RUM | A request appears as a trace in Dash0 within a minute |
| 2 | Data loading | Must | Sessions from the public schedule; sample attendees | Counts match the source; Emma's Monday reads correctly |
| 2b | App shell | Must | Rail nav, dark theme, demo user | Every page loads on desktop and phone width |
| 3 | Search | Must | Hybrid search with keyword fallback; filters from aggregations | The GPU-inference query returns inference-cost talks first |
| 4 | Schedule · For you | Must | For-you filter with folded rows | Emma's day is short and sensible |
| 5 | Dashboard · Now | Should | Stat row and one chart; Now as one card list | Numbers come from aggregations |
| 6 | Profiles · Match | Must | Ranked list with reason chips and a keyword box | Emma's top match shows "University of Utah alumni"; clicking filters |
| 7 | Connect | Should | Request and accept one suggested slot | A meeting appears on both schedules |
| 8 | Ask | Must | Retrieval from Elasticsearch, cited and streamed answer | Trace shows retrieval then the LLM call with tokens and cost |
| 9 | Catch up | Must | Three keynote transcripts; summary and Q&A; sample label visible | A question about a keynote gets a grounded answer |
| 10 | My brief | Could | Drop it; the Dashboard covers it | — |
| 11 | Agenda | Should | Save, clash warnings | Full-day co-located events do not flag every session |
| 12 | Dash0 dashboard and SLO | Should | Product numbers, latency, errors, LLM cost | Agent0 finds a real problem; the fix lands as a pull request |

## Cut line

If time runs short, drop in this order: My brief → Connect → Compare view → Now → Agenda reminders.
Never drop: Search, For you, Match, Ask, Catch up, telemetry.

## Timeline (from kickoff)

| Time | Goal |
|---|---|
| 0:00–0:45 | Pull requests 0, 1, 2b; Gitar live; first trace in Dash0 |
| 0:45–2:00 | Data, search, profiles |
| 2:00–3:30 | For you, Ask, Catch up |
| 3:30–5:00 | Dashboard, Connect, Agenda, Dash0 dashboard; Agent0 moment |
| 5:00–5:45 | Freeze; rehearse twice; record a backup video |
| 5:45 | README final: setup, architecture, tracks, AI use, credits |

## Demo (5 minutes)

1. Dashboard — the conference pulse.
2. Schedule — the GPU-inference search; For you folds the rest.
3. People · Match — top match, click the alumni reason to filter.
4. Ask — a cited, streamed answer.
5. Catch up — a keynote summary and a question.
6. Dash0 — the trace from that chat with tokens and cost; break something, Agent0 finds it, the fix lands as a pull request.
7. GitHub — the pull request list and Gitar reviews.
