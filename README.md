<p align="center">
  <img src="docs/assets/hero.svg" alt="Confox — find the right talk, meet the right people, catch up on what you missed" width="100%">
</p>

<p align="center">
  <a href="https://www.wemakedevs.org"><img alt="WeMakeDevs Cloud Native Hackathon" src="https://img.shields.io/badge/WeMakeDevs-Cloud%20Native%20Hackathon-7c83ff?style=for-the-badge"></a>
  <a href="LICENSE"><img alt="License: Apache 2.0" src="https://img.shields.io/badge/License-Apache%202.0-2ea44f?style=for-the-badge"></a>
  <img alt="Status: building" src="https://img.shields.io/badge/Status-Building%20live-ff8a5c?style=for-the-badge">
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
</p>

---

## Why

KubeCon North America has hundreds of sessions across parallel rooms, thousands of people and only a few days. Attendees miss the talk that mattered, never meet the people they came to meet, and lose the sessions that clashed with something else. People who cannot attend every session in person — because of clashes, caregiving, mobility or hearing — lose the most.

## What Confox does

| | Feature | In one line |
|---|---|---|
| 1 | **Search** | Ask for a talk in your own words; keyword and meaning-based search together. |
| 2 | **Schedule · For you** | Your day, filtered to what fits your profile; everything else folds away. |
| 3 | **People · Match** | People who share your interests, school, company or community, with the reason shown. |
| 4 | **Ask** | Questions about the conference answered with citations to real sessions. |
| 5 | **Catch up** | Summaries, takeaways and Q&A for talks you missed. |
| 6 | **Dashboard · Now** | The conference pulse: what is on now, next, and where the coffee is. |

Feature details and user stories: [docs/idea.md](docs/idea.md).

## Hackathon tracks

| Track | How Confox addresses it |
|---|---|
| Elasticsearch | Elasticsearch is the only data store; hybrid search, aggregations for filters and the dashboard. |
| Dash0 | OpenTelemetry traces, metrics, logs and browser RUM from day one; a product dashboard. |
| Gitar | Every feature lands as a Gitar-reviewed pull request with project-specific review rules. |
| Merge Forward | Catch up makes missed sessions accessible. |

## How it is built

Implementation is described in the docs as each piece lands; every feature is a separate pull request, so the pull request list is the build log.

| Doc | What it covers |
|---|---|
| [Idea](docs/idea.md) | Problem, persona, features, what is out of scope |
| [Plan](docs/plan.md) | Build order, one pull request per feature, cut line |
| [Architecture](docs/architecture.md) | Components and data flow (filled in as we build) |
| [Research](docs/research.md) | Notes gathered before the event: data, search, observability |
| [Data](data/README.md) | What we collected, when, from where, and what is generated |

## Run locally

Needs Docker, [uv](https://docs.astral.sh/uv/) and Node 22+.

```bash
cp .env.example .env    # fill in keys; .env is git-ignored
docker compose up -d    # Elasticsearch on localhost:9200
```

```bash
cd backend && uv sync && uv run uvicorn app.main:app --port 8000 --reload
```

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:5173 — the page shows whether the API and Elasticsearch are up.
How we work (branches, checks, review): [CONTRIBUTING.md](CONTRIBUTING.md).

## Team

<table>
  <tr>
    <td align="center"><a href="https://github.com/riponcm"><img src="https://github.com/riponcm.png?size=120" width="80" alt="riponcm"><br><b>riponcm</b></a></td>
    <td align="center"><a href="https://github.com/FIZ55"><img src="https://github.com/FIZ55.png?size=120" width="80" alt="FIZ55"><br><b>FIZ55</b></a></td>
    <td align="center"><a href="https://github.com/yuzimeng2000-coder"><img src="https://github.com/yuzimeng2000-coder.png?size=120" width="80" alt="yuzimeng2000-coder"><br><b>yuzimeng2000-coder</b></a></td>
  </tr>
</table>

Who built what is visible in the pull requests and commit history.

## AI use

We use [Claude Code](https://claude.com/claude-code) (Anthropic) as a coding assistant. The team decides the design, reviews and tests every change, and can explain every part of the code. Pull requests are also reviewed by Gitar. Any generated sample data in the app is labelled as such.

## Credits

- Schedule data: the public KubeCon + CloudNativeCon North America 2026 schedule on Sessionize ([provenance](data/README.md)).
- Sponsor tools: Elasticsearch, Dash0, Gitar.
- Built at the [WeMakeDevs](https://www.wemakedevs.org) Cloud Native Hackathon, Salt Lake City, November 2026.

## License

[Apache License 2.0](LICENSE)
