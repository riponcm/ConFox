/** Shape of GET /api/dashboard (see backend/app/routers/dashboard.py). */

export const KIND_GROUPS = ['talks', 'keynotes', 'colocated', 'food', 'other'] as const
export type KindGroup = (typeof KIND_GROUPS)[number]
export type KindCounts = Record<KindGroup, number>
export type TimelineBucket = { start: string; total: number; mine: number; kinds: KindCounts }
export type Named = { name: string; count: number; pinned?: boolean }

export type DashboardData = {
  day: string
  now: string
  is_today: boolean
  days: { day: string; sessions: number }[]
  sessions: { total: number; day: number }
  timeline: { interval_minutes: number; buckets: TimelineBucket[]; kind_totals: KindCounts }
  tracks: { name: string; sessions: number }[]
  filling: { id: string; title: string; starts_at: string; room: string; going: number }[]
  my_day: { hours: number; goal_hours: number; sessions: number; meetings: number; requests: number }
  people: {
    total: number
    speakers: number
    attendees: number
    sample: number
    countries: Named[]
    schools: Named[]
    companies: Named[]
    interests: Named[]
  }
  activity: {
    total: number
    sample: number
    kinds: { kind: string; count: number }[]
    buckets: { start: string; count: number }[]
    searches: Named[]
  }
}

/** "2026-11-09T08:40:00" -> "08:40" (schedule times are local and carry no offset). */
export const hhmm = (iso: string) => iso.slice(11, 16)

export const minutesOf = (iso: string) => Number(iso.slice(11, 13)) * 60 + Number(iso.slice(14, 16))

export const hhmmFromMinutes = (m: number) =>
  `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`

/** "2026-11-09" -> "Mon 9" or "Monday, Nov 9". Noon avoids any date shift from the browser's own time zone. */
export function dayLabel(day: string, style: 'short' | 'long' = 'short'): string {
  const d = new Date(`${day}T12:00:00`)
  if (style === 'long') {
    return d.toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })
  }
  return `${d.toLocaleDateString('en-US', { weekday: 'short' })} ${d.getDate()}`
}

export const fmt = (n: number) => n.toLocaleString('en-US')

/** 1 -> "1 session", 2 -> "2 sessions". */
export const plural = (n: number, one: string, many = `${one}s`) => `${fmt(n)} ${n === 1 ? one : many}`

/** Hours with at most one decimal: 8.5 -> "8.5", 8 -> "8", 8.25 -> "8.3". */
export const hours = (h: number) => (Number.isInteger(h) ? String(h) : h.toFixed(1))
