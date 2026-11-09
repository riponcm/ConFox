import { Link } from 'react-router'
import { CalendarRange, Coffee, MapPin, UtensilsCrossed } from 'lucide-react'
import { hhmm, minutes, roomLabel, timeRange } from '../schedule/time.ts'
import SessionLink from '../session/SessionLink.tsx'
import { initials, mealWord } from './types.ts'
import type { Gap, TimelineItem } from './types.ts'

type Row = { kind: 'item'; item: TimelineItem } | { kind: 'gap'; gap: Gap }

/** Compact length for the narrow time column: "15 min", "1h 43m", "8h". */
function span(mins: number): string {
  if (mins < 60) return `${mins} min`
  const h = Math.floor(mins / 60)
  const m = mins % 60
  return m ? `${h}h ${m}m` : `${h}h`
}

/** Items and free windows in one list by start time; a gap sorts after an item starting at the same minute. */
function rows(items: TimelineItem[], gaps: Gap[]): Row[] {
  const all: Row[] = [
    ...items.map((item) => ({ kind: 'item' as const, item })),
    ...gaps.map((gap) => ({ kind: 'gap' as const, gap })),
  ]
  const start = (r: Row) => (r.kind === 'item' ? r.item.starts_at : r.gap.starts_at)
  return all.sort((a, b) => start(a).localeCompare(start(b)) || (a.kind === 'gap' ? 1 : 0) - (b.kind === 'gap' ? 1 : 0))
}

function lead(item: TimelineItem, now: string): string {
  if (item.is_next) {
    if (item.starts_at <= now) return 'now'
    if (item.starts_at.slice(0, 10) === now.slice(0, 10)) return `in ${span(minutes(item.starts_at) - minutes(now))}`
  }
  return span(minutes(item.ends_at) - minutes(item.starts_at))
}

function ItemCard({ item }: { item: TimelineItem }) {
  const next = item.is_next ? <span className="brief-pill">next</span> : null
  if (item.type === 'meeting') {
    return (
      <div className="brief-tl-card brief-tl-meeting">
        <div className="brief-tl-row">
          <span className="avatar avatar-ok avatar-sm" aria-hidden="true">{initials(item.with_name ?? '')}</span>
          <h3>
            {item.title} with {item.with_name ?? 'someone'}
          </h3>
          {next}
        </div>
        {item.room && (
          <p className="brief-tl-sub">
            <MapPin size={14} aria-hidden="true" /> <span>{roomLabel(item.room)}</span>
          </p>
        )}
      </div>
    )
  }
  if (item.type === 'food') {
    const Icon = mealWord(item.title) === 'coffee' ? Coffee : UtensilsCrossed
    return (
      <div className="brief-tl-card brief-tl-food">
        <div className="brief-tl-row">
          <Icon size={16} aria-hidden="true" className="brief-tl-icon" />
          <h3>{item.session_id ? <SessionLink id={item.session_id}>{item.title}</SessionLink> : item.title}</h3>
          {next}
        </div>
        <p className="brief-tl-sub">
          <span>
            <time dateTime={item.starts_at}>{timeRange(item.starts_at, item.ends_at)}</time>
            {item.room ? <> &middot; {roomLabel(item.room)}</> : null}
          </span>
        </p>
      </div>
    )
  }
  return (
    <div className="brief-tl-card brief-tl-session">
      <div className="brief-tl-row">
        <h3 title={item.full_title || item.title}>
          {item.session_id ? <SessionLink id={item.session_id}>{item.title}</SessionLink> : item.title}
        </h3>
        {next}
      </div>
      <p className="brief-tl-sub">
        <span>
          {item.all_day ? 'Co-located, all day' : 'Session'} &middot; until{' '}
          <time dateTime={item.ends_at}>{hhmm(item.ends_at)}</time>
        </span>
      </p>
      {item.room && (
        <p className="brief-tl-sub">
          <MapPin size={14} aria-hidden="true" /> <span>{roomLabel(item.room)}</span>
        </p>
      )}
    </div>
  )
}

export default function DayTimeline({ items, gaps, now }: { items: TimelineItem[]; gaps: Gap[]; now: string }) {
  if (!items.length && !gaps.length) {
    return (
      <p className="brief-empty">
        Nothing on your agenda today. <Link to="/schedule">Browse the schedule</Link>
      </p>
    )
  }
  return (
    <ol className="brief-tl">
      {rows(items, gaps).map((r) => {
        if (r.kind === 'gap') {
          const g = r.gap
          return (
            <li key={`gap-${g.starts_at}`} className="brief-tl-item brief-tl-gap">
              <div className="brief-tl-time">
                <time dateTime={g.starts_at}>{hhmm(g.starts_at)}</time>
                <span>{span(g.minutes)}</span>
              </div>
              <div className="brief-tl-dot" aria-hidden="true" />
              <Link className="brief-tl-card brief-tl-free" to="/schedule">
                <CalendarRange size={15} aria-hidden="true" />
                <span>
                  Free <time dateTime={g.starts_at}>{timeRange(g.starts_at, g.ends_at)}</time> &middot; browse the schedule
                </span>
              </Link>
            </li>
          )
        }
        const it = r.item
        const past = it.ends_at <= now
        return (
          <li
            key={it.id}
            className={`brief-tl-item brief-tl-${it.type}-item${it.is_next ? ' is-next' : ''}${past ? ' is-past' : ''}`}
            aria-current={it.is_next ? 'step' : undefined}
          >
            <div className="brief-tl-time">
              <time dateTime={it.starts_at}>{hhmm(it.starts_at)}</time>
              <span>{lead(it, now)}</span>
            </div>
            <div className="brief-tl-dot" aria-hidden="true" />
            <ItemCard item={it} />
          </li>
        )
      })}
    </ol>
  )
}
