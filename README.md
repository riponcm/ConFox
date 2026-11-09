<p align="center">
  <img src="docs/assets/hero.svg" alt="Confox — find the right talk, meet the right people, catch up on what you missed" width="100%">
</p>

<p align="center">
  <a href="https://www.wemakedevs.org"><img alt="WeMakeDevs Cloud Native Hackathon" src="https://img.shields.io/badge/WeMakeDevs-Cloud%20Native%20Hackathon-7c83ff?style=for-the-badge"></a>
  <a href="LICENSE"><img alt="License: Apache 2.0" src="https://img.shields.io/badge/License-Apache%202.0-2ea44f?style=for-the-badge"></a>
  <a href="https://github.com/riponcm/ConFox/pulls?q=is%3Apr"><img alt="Built PR by PR" src="https://img.shields.io/badge/Built-PR%20by%20PR-ff8a5c?style=for-the-badge"></a>
</p>

<p align="center"><b>Sponsor tools</b></p>
<p align="center">
  <a href="https://www.elastic.co/elasticsearch"><img alt="Elasticsearch" src="https://img.shields.io/badge/Elasticsearch-Search%20%26%20storage-005571?style=for-the-badge&logo=elasticsearch&logoColor=white"></a>
  <a href="https://www.dash0.com"><img alt="Dash0" src="https://img.shields.io/badge/Dash0-Observability-ea3e5c?style=for-the-badge"></a>
  <a href="https://gitar.ai"><img alt="Gitar" src="https://img.shields.io/badge/Gitar-PR%20review-5b2a86?style=for-the-badge"></a>
</p>

<p align="center"><b>Built with</b></p>
<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776ab?style=flat-square&logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white">
  <img alt="React" src="https://img.shields.io/badge/React-19-20232a?style=flat-square&logo=react&logoColor=61dafb">
  <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-3178c6?style=flat-square&logo=typescript&logoColor=white">
  <img alt="Vite" src="https://img.shields.io/badge/Vite-646cff?style=flat-square&logo=vite&logoColor=white">
  <img alt="OpenTelemetry" src="https://img.shields.io/badge/OpenTelemetry-425cc7?style=flat-square&logo=opentelemetry&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-2496ed?style=flat-square&logo=docker&logoColor=white">
  <img alt="Claude" src="https://img.shields.io/badge/Claude-d97757?style=flat-square&logo=claude&logoColor=white">
  <img alt="OpenAI embeddings" src="https://img.shields.io/badge/OpenAI-embeddings-412991?style=flat-square">
</p>

---

## Why

KubeCon North America has hundreds of sessions across parallel rooms, thousands of people and only a few days. Attendees miss the talk that mattered, never meet the people they came to meet, and lose the sessions that clashed with something else. People who cannot attend every session in person, because of clashes, caregiving, mobility or hearing, lose the most.

## What Confox does

The demo follows **Emma**, a platform engineer and University of Utah alumna, at **08:40 on Monday 9 November** (a fixed demo clock, `DEMO_NOW`).

| Page | What it does | Built on |
|---|---|---|
| **Dashboard** | The conference pulse: sessions through the day with a now line, starting soon, top tracks, where attendees come from | Elasticsearch aggregations only |
| **Now** | Next coffee or food ("Coffee Break in 2 h 8 min"), your next agenda item, what is on now and starting soon | `next_food()`, the clock, the agenda index |
| **Schedule** | Day view filtered **For you** (agenda, keynotes, food, interest matches, nearest sessions by meaning); everything else folds away. Search box with hybrid search | BM25 + kNN, fused with RRF |
| **People** | **Match**: people ranked by shared school, company, community, city and interests, each with the reason shown; click a reason to filter by it | Boosted query + vector similarity |
| **Ask** | Questions about the conference answered by Claude with numbered citations to real sessions, streamed, with tokens and cost shown | Retrieval from Elasticsearch, then Claude |
| **Catch up** | Missed a keynote? TL;DR, three takeaways, the transcript and Q&A grounded in it | Transcript chunks in Elasticsearch, Claude |

Feature details and user stories: [docs/idea.md](docs/idea.md).

## Hackathon tracks

| Track | Where to look |
|---|---|
| **Elasticsearch** | Elasticsearch is the only data store (sessions, people, agenda, transcripts). Hybrid search: BM25 and kNN on OpenAI embeddings fused with the native RRF retriever, with a client-side RRF fallback on a basic licence. Facets, the Dashboard and the For-you list are aggregations and filtered queries. See [Search](docs/architecture.md#search-pull-request-3). |
| **Dash0** | OpenTelemetry from the first hour: traces, metrics and logs from the API, browser RUM from the web app, joined into one trace per click. Every Claude call is a `chat {model}` span with GenAI attributes, tokens and cost. Product metrics (searches by mode, matches, chat turns, Claude cost) and a dashboard as code in [dash0/](dash0/README.md). A demo-only endpoint triggers a real Elasticsearch error for Agent0 to find. |
| **Gitar** | Every change landed as a pull request reviewed by Gitar against project rules in [.gitar/review/confox.md](.gitar/review/confox.md). Its findings were fixed in the same pull request and answered in the thread (for example a silent dependency downgrade, a 30 s health-check timeout, a weekday bug in Ask). `main` requires CI and Gitar to pass. |
| **Merge Forward** | Catch up turns a missed talk into readable text: summary, takeaways and grounded Q&A, for people kept away by clashes, caregiving, mobility or hearing. |

## Architecture

```mermaid
flowchart LR
  U[Browser<br/>React + Vite] -->|same-origin /api| A[API<br/>FastAPI]
  U -. RUM, traces .-> D[(Dash0)]
  A -->|BM25, kNN, RRF, aggregations| E[(Elasticsearch 9)]
  A -->|answers, summaries| C[Claude]
  A -->|embeddings| O[OpenAI embeddings]
  A -. traces, metrics, logs .-> D
  S[Public schedule<br/>snapshot] -->|loader| E
```

| Index | Holds |
|---|---|
| `confox-sessions` | 600 sessions from the public schedule, with kind, track, room, speakers and a 1536-d vector |
| `confox-people` | 712 public speaker profiles and 80 sample attendees, with vectors |
| `confox-agenda` | Emma's Monday (sample) |
| `confox-transcripts` | Three sample keynote transcripts in chunks, plus cached summaries |

Design decisions and the conventions every feature follows: [docs/architecture.md](docs/architecture.md).

## Run locally

Needs Docker, [uv](https://docs.astral.sh/uv/) and Node 22+.

```bash
cp .env.example .env
```

Fill in `.env` (it is git-ignored). Everything runs without keys, keyword-only and without Ask; `OPENAI_API_KEY` adds embeddings and hybrid search, `ANTHROPIC_API_KEY` adds Ask and Catch up, and the `OTEL_*` and `VITE_DASH0_*` values send telemetry to Dash0 (the browser token must be ingest-only).

```bash
docker compose up -d
```

```bash
cd backend && uv sync && uv run python -m app.load && uv run python -m app.data.transcripts --load
```

```bash
cd backend && uv run uvicorn app.main:app --port 8000
```

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:5173. The loader prints the counts (600 sessions, 792 people). The Dash0 dashboard imports from [dash0/confox-dashboard.json](dash0/README.md).

Checks, as CI runs them:

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest -q
```

```bash
cd frontend && npm run lint && npm run build
```

## How we built it

The code in this repository was written during the hackathon, one feature per branch and pull request; the [pull request list](https://github.com/riponcm/ConFox/pulls?q=is%3Apr) is the build log. Research and notes gathered before the event are in [docs/research.md](docs/research.md).

| Doc | What it covers |
|---|---|
| [Idea](docs/idea.md) | Problem, persona, features, what is out of scope |
| [Plan](docs/plan.md) | Build order, lanes, cut line, demo script |
| [Architecture](docs/architecture.md) | Components, data, each feature's design, key decisions |
| [Research](docs/research.md) | Notes gathered before the event |
| [Team tasks](docs/tasks/README.md) | Self-contained briefs for team members |
| [Data](data/README.md) | What we collected, when, from where, and what is generated |

## Team

<table>
  <tr>
    <td align="center"><a href="https://github.com/riponcm"><img src="https://github.com/riponcm.png?size=120" width="80" alt="riponcm"><br><b>riponcm</b></a><br><sub>Lead: architecture, backend, integration, reviews</sub></td>
    <td align="center"><a href="https://github.com/FIZ55"><img src="https://github.com/FIZ55.png?size=120" width="80" alt="FIZ55"><br><b>FIZ55</b></a><br><sub>SessionCard component (<a href="https://github.com/riponcm/ConFox/pull/8">#8</a>), used on Schedule and Now</sub></td>
    <td align="center"><a href="https://github.com/yuzimeng2000-coder"><img src="https://github.com/yuzimeng2000-coder.png?size=120" width="80" alt="yuzimeng2000-coder"><br><b>yuzimeng2000-coder</b></a><br><sub><code>next_food()</code> for the Now page (<a href="https://github.com/riponcm/ConFox/pull/17">#17</a>)</sub></td>
  </tr>
</table>

## AI use

Hackathon rule 5 asks us to disclose AI use. Here is all of it:

- **Coding assistants.** Much of the code was written with [Claude Code](https://claude.com/claude-code) (Anthropic). Several features were built in parallel by Claude Code agents from written briefs, each in its own branch; their pull requests say so. yuzimeng2000-coder used OpenAI Codex for #17 and disclosed it in the pull request. The team chose the design, wrote the briefs and review rules, reviewed and tested every change, and can explain every part of the code.
- **Code review.** Every pull request was reviewed by Gitar; its findings and our fixes are in the pull request threads.
- **In the app.** Ask and Catch up call Claude (`claude-opus-5-5`) and show token use and cost. Search and matching use OpenAI `text-embedding-3-small` vectors.
- **Generated data, always labelled.** The 80 attendee profiles and Emma's agenda are generated by seeded code (marked `sample`). The three keynote transcripts were generated by Claude from each talk's public title and description and are labelled in the app as *not the speaker's actual words*. Real attendee data and recordings are not public. See [data/README.md](data/README.md).

## Credits

- Schedule data: the public KubeCon + CloudNativeCon North America 2026 schedule on Sessionize ([provenance](data/README.md)).
- Sponsor tools: [Elasticsearch](https://www.elastic.co/elasticsearch), [Dash0](https://www.dash0.com), [Gitar](https://gitar.ai).
- Built at the [WeMakeDevs](https://www.wemakedevs.org) Cloud Native Hackathon, Salt Lake City, November 2026.

## License

[Apache License 2.0](LICENSE)
