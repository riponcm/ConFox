# Task: SessionCard component

**Owner:** [@FIZ55](https://github.com/FIZ55) · **Branch:** `feat/session-card` · **Area:** frontend only · **Size:** about 60–100 lines

## Context: what Confox is

Confox is a conference guide for KubeCon + CloudNativeCon North America 2026 (Salt Lake City, 9–12 November 2026), built live at the WeMakeDevs Cloud Native Hackathon. It helps an attendee find the right talk, meet the right people and catch up on what they missed. Stack: FastAPI and Elasticsearch on the backend, React 19 + TypeScript + Vite on the frontend, telemetry to Dash0. See [docs/idea.md](../idea.md) and [docs/architecture.md](../architecture.md).

The demo user is **Emma**, a platform engineer and University of Utah alumna, on Monday 9 November at 8:40 AM.

## What to build

A reusable React component that shows one session as a card. Search (PR 3), Schedule (PR 4) and Now (PR 5) will all render lists of these, so it must be small, predictable and look right in a narrow phone column.

### Files

| File | Action |
|---|---|
| `frontend/src/types.ts` | Create. Export the `Session` type below. |
| `frontend/src/components/SessionCard.tsx` | Create. Default export `SessionCard`. |
| `frontend/src/index.css` | Add the card styles at the end, under a `/* SessionCard */` comment. Reuse the existing CSS variables. |

Do not change any other file. Do not wire the card into a page; the feature pull requests do that.

### The data (exactly what the API returns for a session)

```ts
export type SessionKind =
  | 'keynote' | 'talk' | 'lightning' | 'tutorial' | 'contribfest'
  | 'poster' | 'showcase' | 'colocated' | 'break' | 'registration'

export type Session = {
  id: string
  title: string
  description?: string
  starts_at: string        // local conference time, no offset: "2026-11-09T10:48:00"
  ends_at: string          // "2026-11-09T11:03:00"
  day: string              // "2026-11-09"
  minutes: number          // 15
  kind: SessionKind
  is_food: boolean         // true for coffee, lunch, breakfast, receptions
  track: string | null     // "AI Inference + Agentic"
  level: string | null     // "Beginner" | "Advanced" | "Any Level" | null
  projects: string[]       // ["Kubeflow", "KServe"]
  room: string             // "Hyatt Regency | Level 4 | Regency Ballroom B-D"
  venue: string            // "Hyatt Regency"
  speaker_names: string[]
  companies: string[]
}
```

### The component

```ts
type Props = {
  session: Session
  onSelect?: (session: Session) => void   // when given, the whole card is a button
  aside?: React.ReactNode                  // optional slot on the right, e.g. an "Add" button later
}
```

It shows:

1. **Time:** `10:48–11:03` (24-hour, from `starts_at`/`ends_at`). Parse the string's hour and minute directly; do **not** use `new Date()`, because the times have no offset and must not shift to the viewer's time zone. Add the duration in muted text when it is 60 minutes or more (`· 2 h 30 min`).
2. **Title:** at most 2 lines, then an ellipsis.
3. **Kind badge:** a small pill with a readable label (`Keynote`, `Talk`, `Lightning`, `Tutorial`, `Contribfest`, `Poster`, `Showcase`, `Co-located`, `Break`, `Registration`). Breaks with `is_food` say `Food` and use the `--warn` / `--warn-soft` colours; keynotes use `--accent` / `--accent-soft`; everything else is neutral (`--panel-2`, `--text-2`).
4. **Where:** the room, shortened to the part after the venue (`Level 4 | Regency Ballroom B-D`), with a `MapPin` icon.
5. **Who:** up to 2 speaker names, then `+N` (`Ana Ruiz, Ben Cole +2`). Hide the line when there are no speakers.
6. **Track** in muted text when present.

### Rules (from `.gitar/review/confox.md`)

- No emoji anywhere, in UI text or code. Icons only from `lucide-react` (already installed): use `Clock`, `MapPin`, `Users`.
- Colours only through the CSS variables in `frontend/src/index.css` (`--panel`, `--panel-2`, `--line`, `--text`, `--text-2`, `--muted`, `--accent`, `--accent-soft`, `--warn`, `--warn-soft`). No hex or `rgb()` in the component.
- Works at 375 px wide: long titles and room names wrap or truncate; nothing causes horizontal scroll.
- Accessible: when `onSelect` is given, render a `<button type="button">` (keyboard and focus work); otherwise an `<article>`. Icons are `aria-hidden`. Give the time a `<time dateTime={starts_at}>`.

### Sample data to develop with

Put these in a scratch page locally while you build, then remove the scratch code before committing (do not commit it):

```ts
const samples: Session[] = [
  { id: 'a', title: 'Coffee Break', starts_at: '2026-11-09T10:48:00', ends_at: '2026-11-09T11:03:00', day: '2026-11-09', minutes: 15, kind: 'break', is_food: true, track: 'Project Lightning Talks', level: null, projects: [], room: 'Hyatt Regency | Level 4 | Regency Ballroom B-D', venue: 'Hyatt Regency', speaker_names: [], companies: [] },
  { id: 'b', title: 'Cloud Native AI + Inference Day Hosted by CNCF - Full Day Event | ALL ACCESS PASS REQUIRED', starts_at: '2026-11-09T09:00:00', ends_at: '2026-11-09T17:30:00', day: '2026-11-09', minutes: 510, kind: 'colocated', is_food: false, track: 'CNCF-hosted Co-located Events', level: null, projects: [], room: 'Salt Palace | Level 2 | 254', venue: 'Salt Palace', speaker_names: [], companies: [] },
  { id: 'c', title: 'Serving LLMs on Shared GPUs Without Losing Sleep', starts_at: '2026-11-10T11:15:00', ends_at: '2026-11-10T11:45:00', day: '2026-11-10', minutes: 30, kind: 'talk', is_food: false, track: 'AI Inference + Agentic', level: 'Advanced', projects: ['KServe'], room: 'Salt Palace | Level 1 | Grand Ballroom ACE', venue: 'Salt Palace', speaker_names: ['Ana Ruiz', 'Ben Cole', 'Chen Wei', 'Dara Okafor'], companies: [] },
]
```

## Done when

- [ ] `cd frontend && npm install && npm run lint && npm run build` passes.
- [ ] The three samples render correctly at 375 px and at desktop width (attach two screenshots to the pull request).
- [ ] No emoji, no hard-coded colours, no `new Date()` on the session times.
- [ ] Only the three files above changed.

## Open the pull request

```bash
git checkout -b feat/session-card
# build, then:
git add frontend/src/types.ts frontend/src/components/SessionCard.tsx frontend/src/index.css
git commit -m "Add SessionCard component"
git push -u origin feat/session-card
gh pr create --base main --title "SessionCard component" --body "Implements docs/tasks/session-card.md. Screenshots: ..."
```
