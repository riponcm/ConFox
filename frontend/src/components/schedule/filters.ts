import { durationMin } from './time.ts'
import type { AgendaItem, DayResponse, FacetName, ScheduleSession } from './types.ts'

// The Schedule page keeps its state in the URL query so a reload (or a shared link) shows the same view:
// ?day=2026-11-09&view=all&from=day&sort=going&kind=lightning&kind=talk&friends=1&topic=KServe&q=gpu
// Defaults are left out of the URL.

export type View = 'foryou' | 'all'
export type From = 'now' | 'day'
export type Sort = 'time' | 'fit' | 'going'

export const FACETS: FacetName[] = ['kind', 'track', 'level', 'venue']
export const FACET_LABELS: Record<FacetName, string> = { kind: 'Kind', track: 'Track', level: 'Level', venue: 'Venue' }
export const TOGGLES = [
  { key: 'mine', label: 'On my agenda' },
  { key: 'friends', label: 'Friends going' },
  { key: 'noclash', label: 'No clashes' },
] as const
export type Toggle = (typeof TOGGLES)[number]['key']
export const SORTS: { key: Sort; label: string }[] = [
  { key: 'time', label: 'Time' },
  { key: 'fit', label: 'Best match' },
  { key: 'going', label: 'Most going' },
]

export type Filters = Record<FacetName, string[]> & Record<Toggle, boolean> & { topics: string[] }

export type ScheduleState = {
  day: string | null
  view: View
  /** null: the default for the day (From now today, Whole day on other days). */
  from: From | null
  sort: Sort
  q: string
  filters: Filters
}

export const NO_FILTERS: Filters = {
  kind: [],
  track: [],
  level: [],
  venue: [],
  mine: false,
  friends: false,
  noclash: false,
  topics: [],
}

const pick = <T extends string>(value: string | null, allowed: readonly T[]): T | null =>
  allowed.includes(value as T) ? (value as T) : null

export function parseState(params: URLSearchParams): ScheduleState {
  const many = (name: string) => [...new Set(params.getAll(name).filter(Boolean))]
  return {
    day: params.get('day'),
    view: pick(params.get('view'), ['foryou', 'all'] as const) ?? 'foryou',
    from: pick(params.get('from'), ['now', 'day'] as const),
    sort: pick(params.get('sort'), ['time', 'fit', 'going'] as const) ?? 'time',
    q: params.get('q') ?? '',
    filters: {
      kind: many('kind'),
      track: many('track'),
      level: many('level'),
      venue: many('venue'),
      mine: params.get('mine') === '1',
      friends: params.get('friends') === '1',
      noclash: params.get('noclash') === '1',
      topics: many('topic'),
    },
  }
}

export function toParams(s: ScheduleState): URLSearchParams {
  const p = new URLSearchParams()
  if (s.day) p.set('day', s.day)
  if (s.view !== 'foryou') p.set('view', s.view)
  if (s.from) p.set('from', s.from)
  if (s.sort !== 'time') p.set('sort', s.sort)
  if (s.q) p.set('q', s.q)
  for (const f of FACETS) for (const v of s.filters[f]) p.append(f, v)
  for (const t of TOGGLES) if (s.filters[t.key]) p.set(t.key, '1')
  for (const v of s.filters.topics) p.append('topic', v)
  return p
}

/** Filters chosen in the Filters panel (facet values and toggles); interest chips are shown on their own. */
export function panelCount(f: Filters): number {
  return FACETS.reduce((n, k) => n + f[k].length, 0) + TOGGLES.filter((t) => f[t.key]).length
}

export function anyFilter(f: Filters): boolean {
  return panelCount(f) > 0 || f.topics.length > 0
}

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** Same rule as the API's interest match: the phrase as whole words, any case, in title, track, projects or text. */
export function mentions(s: ScheduleSession, phrase: string): boolean {
  const re = new RegExp(`\\b${escape(phrase.trim())}\\b`, 'i')
  const text = [s.title, s.track ?? '', (s.projects ?? []).join(' '), s.description ?? ''].join('\n')
  return re.test(text)
}

/** Whether a session passes the filters. Items on the agenda always pass No clashes: they are the plan. */
export function keepSession(s: ScheduleSession, f: Filters): boolean {
  for (const k of FACETS) if (f[k].length && !f[k].includes(s[k] ?? '')) return false
  if (f.mine && !s.on_agenda) return false
  if (f.friends && !(s.going_names ?? []).length) return false
  if (f.noclash && (s.clashes ?? []).length && !s.on_agenda) return false
  if (f.topics.length && !f.topics.some((t) => mentions(s, t))) return false
  return true
}

/** The day with filters and From now applied. Meetings and requests stay unless they have ended. */
export function applyFilters(data: DayResponse, f: Filters, fromNow: boolean): DayResponse {
  const live = <T extends { ends_at: string }>(x: T) => !fromNow || x.ends_at > data.now
  const liveItem = (i: AgendaItem) => live(i)
  return {
    ...data,
    sessions: data.sessions.filter((s) => live(s) && keepSession(s, f)),
    meetings: data.meetings.filter(liveItem),
    pending: data.pending.filter(liveItem),
  }
}

/** Sessions for the ranked (non-time) views, best first; start time breaks ties. */
export function sortSessions(list: ScheduleSession[], sort: Sort): ScheduleSession[] {
  const key = (s: ScheduleSession) => (sort === 'going' ? (s.going ?? 0) : (s.fit ?? 0))
  const second = (s: ScheduleSession) => (sort === 'going' ? (s.fit ?? 0) : (s.going ?? 0))
  return [...list].sort(
    (a, b) =>
      key(b) - key(a) ||
      second(b) - second(a) ||
      (a.starts_at < b.starts_at ? -1 : a.starts_at > b.starts_at ? 1 : 0) ||
      durationMin(a) - durationMin(b),
  )
}

/** "Alice Moreno going", "Quinn Park +2 going", "3 going"; empty when nobody else saved it. */
export function goingLabel(s: ScheduleSession): string {
  const going = s.going ?? 0
  const names = s.going_names ?? []
  if (!going) return ''
  if (!names.length) return `${going} going`
  const first = names[0].split(' ')[0]
  return going > 1 ? `${first} +${going - 1} going` : `${first} going`
}

/** "Alice Moreno, Quinn Park and 3 others saved this" */
export function goingTitle(s: ScheduleSession): string {
  const names = s.going_names ?? []
  const others = (s.going ?? 0) - names.length
  if (!names.length) return `${s.going ?? 0} ${s.going === 1 ? 'attendee' : 'attendees'} saved this`
  const rest = others > 0 ? ` and ${others} ${others === 1 ? 'other' : 'others'}` : ''
  return `${names.join(', ')}${rest} saved this`
}
