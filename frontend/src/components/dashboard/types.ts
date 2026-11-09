/** Shape of GET /api/dashboard (see backend/app/routers/dashboard.py). */

export type Group = 'talks' | 'keynotes' | 'colocated' | 'breaks' | 'other'

export type TimelineBucket = { start: string; total: number; counts: Record<Group, number> }

export type DashboardData = {
  day: string
  now: string
  is_today: boolean
  days: { day: string; sessions: number }[]
  stats: {
    sessions_total: number
    sessions_day: number
    speakers_total: number
    speakers_day: number
    tracks_total: number
    tracks_day: number
    sample_attendees: number
    countries: number
  }
  timeline: { interval_minutes: number; groups: Group[]; buckets: TimelineBucket[] }
  next_up: { id: string; title: string; starts_at: string; room: string; kind: string }[]
  next_up_total: number
  tracks: { name: string; sessions: number }[]
  kinds: { kind: string; sessions: number }[]
  people: {
    countries: { name: string; attendees: number }[]
    companies: { name: string; speakers: number }[]
  }
}

// Fixed order, fixed colour: a group keeps its colour whatever the day shows.
export const GROUPS: { id: Group; label: string; color: string }[] = [
  { id: 'talks', label: 'Talks', color: 'var(--chart-1)' },
  { id: 'keynotes', label: 'Keynotes', color: 'var(--chart-2)' },
  { id: 'colocated', label: 'Co-located', color: 'var(--chart-3)' },
  { id: 'breaks', label: 'Breaks and food', color: 'var(--chart-4)' },
  { id: 'other', label: 'Other', color: 'var(--chart-5)' },
]

const GROUP_OF_KIND: Record<string, Group> = {
  talk: 'talks',
  lightning: 'talks',
  tutorial: 'talks',
  contribfest: 'talks',
  keynote: 'keynotes',
  colocated: 'colocated',
  break: 'breaks',
}

export function groupOf(kind: string): (typeof GROUPS)[number] {
  const id = GROUP_OF_KIND[kind] ?? 'other'
  return GROUPS.find((g) => g.id === id) ?? GROUPS[GROUPS.length - 1]
}

/** "2026-11-09T08:40:00" -> "08:40" (schedule times are local and carry no offset). */
export const hhmm = (iso: string) => iso.slice(11, 16)

export const minutesOf = (iso: string) => Number(iso.slice(11, 13)) * 60 + Number(iso.slice(14, 16))

export const hhmmFromMinutes = (m: number) =>
  `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`

/** "2026-11-09" -> "Mon 9 Nov". Noon avoids any date shift from the browser's own time zone. */
export function dayLabel(day: string, style: 'short' | 'long' = 'short'): string {
  const d = new Date(`${day}T12:00:00`)
  const weekday = d.toLocaleDateString('en-US', { weekday: style === 'long' ? 'long' : 'short' })
  const month = d.toLocaleDateString('en-US', { month: 'short' })
  return style === 'long' ? `${weekday} ${d.getDate()} ${month}` : `${weekday} ${d.getDate()}`
}

export const fmt = (n: number) => n.toLocaleString('en-US')
