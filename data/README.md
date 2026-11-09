# Data

Where every dataset comes from, when it was collected, and whether it is real or generated.
Nothing here is private or behind a login.

## Collected (real, public)

| File | Source | Collected | Contents |
|---|---|---|---|
| `raw/sessionize-kubecon-na-2026.json` | Public Sessionize feed for KubeCon + CloudNativeCon North America 2026: `https://sessionize.com/api/v2/svi82w6c/view/All` | 2026-11-09 18:28 UTC (during the hackathon) | 600 sessions, 712 speakers, 37 rooms, 7 category groups, 11 session questions |

Sessions per day in this snapshot:

| Day | Sessions |
|---|---|
| Sun 8 Nov | 4 (registration) |
| Mon 9 Nov | 78 (co-located events) |
| Tue 10 Nov | 194 |
| Wed 11 Nov | 203 |
| Thu 12 Nov | 121 |

The file is kept exactly as fetched (sha256 starts `77e3b97745794842`) so loaders can be re-run against the same input. Speaker names, bios and links are the public profiles the conference publishes; we use them only to show who is speaking.

During research before the event we read the same feed (about 598 sessions at the time) to plan the data model; the schedule changes as the organisers edit it, so the snapshot above is the one the app uses.

To refresh it:

```bash
curl -fsSL https://sessionize.com/api/v2/svi82w6c/view/All -o data/raw/sessionize-kubecon-na-2026.json
```

## Generated during development (sample, labelled)

These are created by the app's own loaders in later pull requests and are fictional. The UI labels them as sample data.

| Dataset | Why it is generated | Added in |
|---|---|---|
| Sample attendees | Real attendee profiles are private; Emma and about 80 fictional attendees stand in (University of Utah first) | Pull request 2 |
| Sample agenda and meetings | Emma's Monday for the demo: a co-located AI day, a coffee, a pending lunch request | Pull request 2 |
| Sample talk transcripts (`sample/transcripts.json`) | Recordings are not public yet. Three Tuesday 10 November keynotes (sessions 1301696, 1349401, 1301749); Claude (`claude-opus-5-5`) wrote about 1300 words for each from the keynote's public title, speakers and description only, on 2026-11-09. Generated once with `uv run python -m app.data.transcripts --generate`; `--load` indexes it without calling Claude | Pull request 9 |
| Embeddings | Vectors computed from the text above for hybrid search and matching | Pull requests 2, 3 |

## Rules

- Only public data or data we generate; no scraped private profiles, no login-protected content.
- Raw files stay unmodified; loaders transform them on the way into Elasticsearch.
- Generated data is always labelled as sample in the UI.
