import type { Session } from '../../types.ts'

// Shapes returned by /api/schedule and /api/search. Kept local to the Schedule feature.

export type ScheduleSession = {
  id: string
  title: string
  description?: string
  starts_at: string
  ends_at: string
  day: string
  kind: string
  is_food?: boolean
  track?: string | null
  level?: string | null
  projects?: string[]
  room?: string
  venue?: string
  speaker_names?: string[]
  // Added by /api/schedule/day; absent on search results.
  for_you?: boolean
  why?: string[]
  fit?: number
  on_agenda?: boolean
  clashes?: string[]
  // Added by /api/search.
  score?: number
}

export type AgendaItem = {
  id: string
  kind: 'session' | 'meeting'
  status: 'confirmed' | 'pending' | 'declined'
  /** Meetings only; a pending meeting without one is a request someone sent the user. */
  direction?: 'incoming' | 'outgoing'
  title: string
  starts_at: string
  ends_at: string
  room?: string
  with_name?: string
  session_id?: string
}

export type DayResponse = {
  day: string
  now: string
  sessions: ScheduleSession[]
  meetings: AgendaItem[]
  pending: AgendaItem[]
  semantic: boolean
}

/** GET /api/agenda */
export type AgendaResponse = { items: AgendaItem[]; pending: AgendaItem[] }

export type DaysResponse = { days: { day: string; count: number }[] }

export type Meta = { now: string; user_id: string }

export type Bucket = { key: string; count: number }

export type SearchResponse = {
  mode: string
  took_ms: number
  total: number
  // The search API returns every session field, so results also fit the shared Session type.
  results: (Session & { score?: number })[]
  facets?: Partial<Record<'day' | 'kind' | 'track' | 'level', Bucket[]>>
}
