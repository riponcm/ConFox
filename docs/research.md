# Research notes

Gathered before the event (reading docs, testing services, planning). No product code lives here.

## Data

- The KubeCon NA 2026 schedule is published on Sessionize with a public JSON feed: sessions, speakers, rooms, tracks and times.
- Session kinds need deriving from track and title (keynote, talk, lightning, break, food, co-located day). Titles can start with emoji, so text is normalised before classifying.
- Co-located events on Monday run all day; treating them as normal sessions would make every other session look like a clash.
- Attendee profiles are not public, so the demo uses generated sample attendees, clearly labelled.
- The snapshot the app uses and its provenance: [data/README.md](../data/README.md).

## Search (Elasticsearch)

- Hybrid search: BM25 keyword relevance plus vector similarity, fused by rank (reciprocal rank fusion). Keyword search alone misses paraphrases; vectors alone miss exact names such as project names.
- A keyword-only fallback keeps search working when no embedding key is present.
- Aggregations can drive filters, facets and dashboard numbers directly, so the store and the analytics are the same system.
- Elasticsearch 9 leaves dense vectors out of `_source` by default; code that needs a stored vector must request it explicitly.
- Re-creating one index must never touch the others.

## Observability (Dash0)

- Dash0 ingests OpenTelemetry over OTLP (HTTP); the API exports traces, metrics and logs; the browser SDK sends RUM and propagates trace context to the API.
- The browser token ships to every visitor, so it must be an ingest-only token.
- LLM spans should carry model, tokens and cost; the cost table must include the model in use or cost reads zero.
- Dashboards are Perses JSON; fixed rate windows of a few minutes read better on low traffic than automatic ones.

## Accessibility (Merge Forward)

People miss sessions for reasons beyond choice: schedule clashes, caregiving, mobility, hearing. A text-first Catch up with summaries, takeaways and Q&A over the transcript lets them recover what they missed.

## Risks

| Risk | Mitigation |
|---|---|
| Venue Wi-Fi | Everything runs locally except LLM and telemetry calls; record a backup demo video |
| LLM latency on stage | Stream answers |
| Running out of time | Cut line in [plan.md](plan.md) |
