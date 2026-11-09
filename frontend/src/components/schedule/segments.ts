import { minutes } from './time.ts'
import type { AgendaItem, DayResponse, ScheduleSession } from './types.ts'

export type Entry =
  | { type: 'session'; id: string; start: string; session: ScheduleSession }
  | { type: 'meeting'; id: string; start: string; item: AgendaItem }

/** A time block of visible entries, or a fold of consecutive sessions hidden in For you mode. */
export type Segment = { type: 'block' | 'fold'; key: string; start: string; entries: Entry[] }

function entries(data: DayResponse): Entry[] {
  const meetings: Entry[] = [...data.meetings, ...data.pending].map((item) => ({
    type: 'meeting',
    id: `m-${item.id}`,
    start: item.starts_at,
    item,
  }))
  const sessions: Entry[] = data.sessions.map((session) => ({
    type: 'session',
    id: session.id,
    start: session.starts_at,
    session,
  }))
  // Within one start time: meetings first, then For you sessions by fit, then the rest in schedule order.
  const rank = (e: Entry) => (e.type === 'meeting' ? 0 : e.session.for_you ? 1 : 2)
  const fit = (e: Entry) => (e.type === 'session' ? (e.session.fit ?? 0) : 1)
  return [...meetings, ...sessions]
    .map((e, i) => ({ e, i }))
    .sort((a, b) => {
      if (a.e.start !== b.e.start) return a.e.start < b.e.start ? -1 : 1
      return rank(a.e) - rank(b.e) || fit(b.e) - fit(a.e) || a.i - b.i
    })
    .map(({ e }) => e)
}

export function buildSegments(data: DayResponse, forYouOnly: boolean): Segment[] {
  const out: Segment[] = []
  for (const e of entries(data)) {
    const visible = !forYouOnly || e.type === 'meeting' || e.session.for_you
    const last = out[out.length - 1]
    if (visible) {
      if (last?.type === 'block' && last.start === e.start) last.entries.push(e)
      else out.push({ type: 'block', key: `b-${e.id}`, start: e.start, entries: [e] })
    } else if (last?.type === 'fold') {
      last.entries.push(e)
    } else {
      out.push({ type: 'fold', key: `f-${e.id}`, start: e.start, entries: [e] })
    }
  }
  return out
}

/** Group entries by start time, for rendering an expanded fold. */
export function byStart(list: Entry[]): [string, Entry[]][] {
  const groups = new Map<string, Entry[]>()
  for (const e of list) groups.set(e.start, [...(groups.get(e.start) ?? []), e])
  return [...groups]
}

/** Index of the segment the "now" line goes before: the first that starts at or after now. */
export function nowIndex(segments: Segment[], now: string): number {
  const at = minutes(now)
  const i = segments.findIndex((s) => minutes(s.start) >= at)
  return i === -1 ? segments.length : i
}
