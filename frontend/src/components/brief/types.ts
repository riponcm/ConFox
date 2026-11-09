import type { Session } from '../../types.ts'

export type TimelineItem = {
  id: string
  type: 'session' | 'meeting' | 'food'
  title: string
  full_title: string
  starts_at: string
  ends_at: string
  room: string
  with_id: string | null
  with_name: string | null
  session_id: string | null
  status: string
  all_day: boolean
  is_next: boolean
}

export type Gap = { starts_at: string; ends_at: string; minutes: number }

export type MeetingRequest = {
  id: string
  with_id: string | null
  with_name: string
  title: string
  starts_at: string
  ends_at: string
  room: string
  message: string
  session_id: string | null
  direction: 'incoming' | 'outgoing'
}

export type FreeAt = { starts_at: string; ends_at: string; title: string; room: string }

export type SuggestedPerson = {
  id: string
  name: string
  title: string
  company: string
  kind: string
  sample: boolean
  reason: string
  free_at: FreeAt | null
}

export type SuggestedSession = Session & { why: string[]; fit: number }

export type BriefResponse = {
  now: string
  day: string
  user: { id: string; name: string; first_name: string; title: string; company: string; school: string; interests: string[] }
  summary: string
  timeline: TimelineItem[]
  gaps: Gap[]
  requests: { incoming: MeetingRequest[]; outgoing: MeetingRequest[] }
  people: SuggestedPerson[]
  suggested: SuggestedSession[]
  food: { session: Session; status: 'now' | 'next'; minutes: number } | null
}

/** "Alice Moreno" -> "AM" */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  return ((parts[0]?.[0] ?? '') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase() || '?'
}

export function firstName(name: string): string {
  return name.trim().split(/\s+/)[0] || name
}

/** A food break named the way people say it: "lunch" or "coffee". */
export function mealWord(title: string): string {
  return /lunch/i.test(title) ? 'lunch' : /breakfast/i.test(title) ? 'breakfast' : 'coffee'
}

/** "2026-11-09" -> "Monday, November 9", fixed to the calendar date whatever the browser's zone. */
export function longDay(day: string): string {
  const [y, m, d] = day.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    timeZone: 'UTC',
  })
}
