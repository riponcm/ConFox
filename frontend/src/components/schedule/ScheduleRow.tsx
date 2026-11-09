import { Clock, TriangleAlert, Users, UsersRound } from 'lucide-react'
import AgendaButton from './AgendaButton.tsx'
import KindIcon from './KindIcon.tsx'
import { canAdd, type ToggleAgenda } from './agenda.ts'
import { goingLabel, goingTitle } from './filters.ts'
import { durationMin, hhmm, roomLabel } from './time.ts'
import type { AgendaItem, ScheduleSession } from './types.ts'

type Props = {
  session: ScheduleSession
  muted?: boolean
  /** Ranked views have no time column, so the row shows its own start and end. */
  showTime?: boolean
  onToggleAgenda?: ToggleAgenda
}

export function TimeRange({ start, end }: { start: string; end: string }) {
  return (
    <span className="sch-range">
      <time dateTime={start}>{hhmm(start)}</time>&ndash;<time dateTime={end}>{hhmm(end)}</time>
    </span>
  )
}

export function Duration({ min }: { min: number }) {
  return <time dateTime={`PT${min}M`}>{min} min</time>
}

/** Track, reasons, who is going and what it overlaps, as one wrapping row of chips. */
export function SessionChips({ session: s }: { session: ScheduleSession }) {
  const why = (s.why ?? []).filter((w) => w !== 'on your agenda')
  const going = goingLabel(s)
  const clashes = s.clashes ?? []
  if (!s.track && !why.length && !going && !clashes.length) return null
  return (
    <ul className="chips sch-chips">
      {s.track && <li className="chip chip-track">{s.track}</li>}
      {why.map((w) => (
        <li key={w} className="chip">
          {w}
        </li>
      ))}
      {going && (
        <li className="chip chip-going" title={goingTitle(s)}>
          <UsersRound size={12} aria-hidden="true" />
          <span>{going}</span>
          <span className="sch-sr-only">: {goingTitle(s)}</span>
        </li>
      )}
      {clashes.map((c) => (
        <li key={c} className="chip chip-warn">
          <TriangleAlert size={12} aria-hidden="true" />
          overlaps {c}
        </li>
      ))}
    </ul>
  )
}

export function ScheduleRow({ session: s, muted = false, showTime, onToggleAgenda }: Props) {
  const room = roomLabel(s.room)
  const classes = ['sch-row', muted && 'is-muted', s.on_agenda && 'is-agenda'].filter(Boolean).join(' ')
  return (
    <li className={classes}>
      <div className="sch-body">
        <p className="sch-title">
          <KindIcon kind={s.kind} isFood={s.is_food} />
          <span>{s.title}</span>
        </p>
        <p className="sch-meta">
          {showTime && (
            <span>
              <TimeRange start={s.starts_at} end={s.ends_at} />
            </span>
          )}
          {room && <span>{room}</span>}
          <span>
            <Duration min={durationMin(s)} />
          </span>
          {s.level && <span>{s.level}</span>}
        </p>
        <SessionChips session={s} />
      </div>
      {onToggleAgenda && canAdd(s) && (
        <div className="sch-action">
          <AgendaButton title={s.title} on={!!s.on_agenda} onToggle={() => onToggleAgenda(s.id, !!s.on_agenda)} />
        </div>
      )}
    </li>
  )
}

export function MeetingRow({ item }: { item: AgendaItem }) {
  const pending = item.status === 'pending'
  const outgoing = pending && item.direction === 'outgoing'
  const title = item.with_name ? `${item.title} with ${item.with_name}` : item.title
  const room = roomLabel(item.room)
  return (
    <li className={pending ? 'sch-row sch-meeting is-pending' : 'sch-row sch-meeting'}>
      <div className="sch-body">
        <p className="sch-title">
          <span className="sch-kind" aria-hidden="true">
            {pending ? <Clock size={14} /> : <Users size={14} />}
          </span>
          <span>{title}</span>
        </p>
        <p className="sch-meta">
          <span>{outgoing ? 'Request sent' : pending ? 'Meeting request' : 'Meeting'}</span>
          <span>
            <TimeRange start={item.starts_at} end={item.ends_at} />
          </span>
          {room && <span>{room}</span>}
          {!room && pending && <span>Place not set</span>}
        </p>
        {pending && (
          <ul className="chips sch-chips">
            <li className="chip chip-warn">Pending</li>
          </ul>
        )}
      </div>
    </li>
  )
}
