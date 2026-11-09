// Schedule times are local conference time without an offset ("2026-11-09T10:48:00"). They are read as
// strings so nothing is shifted into the browser's time zone.

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

/** "2026-11-09T10:48:00" -> "10:48" */
export function hhmm(iso: string): string {
  return iso.slice(11, 16)
}

/** "2026-11-09T10:48:00" -> 648 (minutes after midnight) */
export function minutes(iso: string): number {
  return Number(iso.slice(11, 13)) * 60 + Number(iso.slice(14, 16))
}

export function timeRange(start: string, end: string): string {
  return `${hhmm(start)}–${hhmm(end)}`
}

/** "2026-11-09" -> "Mon 9". Date.UTC keeps the calendar date fixed whatever the browser's zone. */
export function dayLabel(day: string): string {
  const [y, m, d] = day.split('-').map(Number)
  return `${WEEKDAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()]} ${d}`
}

/** "Salt Palace | Level 2 | 254" -> "Level 2 · 254": the venue is implied by the room. */
export function roomLabel(room?: string): string {
  if (!room) return ''
  const parts = room.split('|').map((p) => p.trim()).filter(Boolean)
  return (parts.length > 1 ? parts.slice(1) : parts).join(' · ')
}

const KIND_LABELS: Record<string, string> = {
  keynote: 'Keynote',
  talk: 'Talk',
  lightning: 'Lightning talk',
  tutorial: 'Tutorial',
  contribfest: 'ContribFest',
  poster: 'Poster',
  showcase: 'Showcase',
  colocated: 'Co-located event',
  break: 'Break',
}

export function kindLabel(kind: string, isFood?: boolean): string {
  if (kind === 'break' && isFood) return 'Food and coffee'
  return KIND_LABELS[kind] ?? kind
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const WEEKDAYS_LONG = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
const MONTHS_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
  'October', 'November', 'December']

function parts(day: string): { weekday: number; month: number; date: number } {
  const [y, m, d] = day.split('-').map(Number)
  return { weekday: new Date(Date.UTC(y, m - 1, d)).getUTCDay(), month: m - 1, date: d }
}

/** "2026-11-09" -> "Mon" */
export function weekday(day: string): string {
  return WEEKDAYS[parts(day).weekday]
}

/** "2026-11-09" -> "Mon, Nov 9" */
export function shortDate(day: string): string {
  const p = parts(day)
  return `${WEEKDAYS[p.weekday]}, ${MONTHS[p.month]} ${p.date}`
}

/** "2026-11-09" -> "Monday 9 November", for screen readers. */
export function longDate(day: string): string {
  const p = parts(day)
  return `${WEEKDAYS_LONG[p.weekday]} ${p.date} ${MONTHS_LONG[p.month]}`
}

/** Length in minutes, from the strings (the loader's `minutes` when present). */
export function durationMin(s: { starts_at: string; ends_at: string; minutes?: number }): number {
  return s.minutes ?? Math.max(0, minutes(s.ends_at) - minutes(s.starts_at))
}
