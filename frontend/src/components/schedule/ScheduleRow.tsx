import { CalendarCheck, Clock, TriangleAlert, Users } from 'lucide-react'
import AgendaButton from './AgendaButton.tsx'
import { canAdd, type ToggleAgenda } from './agenda.ts'
import { kindLabel, roomLabel, timeRange } from './time.ts'
import type { AgendaItem, ScheduleSession } from './types.ts'

type Props = { session: ScheduleSession; muted?: boolean; showDay?: string; onToggleAgenda?: ToggleAgenda }

export function ScheduleRow({ session: s, muted = false, showDay, onToggleAgenda }: Props) {
  const room = roomLabel(s.room)
  const why = s.why ?? []
  const clashes = s.clashes ?? []
  const classes = ['sch-row', muted && 'is-muted', s.on_agenda && 'is-agenda'].filter(Boolean).join(' ')
  return (
    <li className={classes}>
      <span className="sch-time">
        {showDay && <span className="sch-time-day">{showDay}</span>}
        {timeRange(s.starts_at, s.ends_at)}
      </span>
      <div className="sch-body">
        <p className="sch-title">
          {s.on_agenda && <CalendarCheck size={14} className="sch-title-icon" aria-label="On your agenda" />}
          {s.title}
        </p>
        <p className="sch-meta">
          <span>{kindLabel(s.kind, s.is_food)}</span>
          {room && <span>{room}</span>}
        </p>
        {why.length > 0 && (
          <ul className="chips sch-why" aria-label="Why this is for you">
            {why.map((w) => (
              <li key={w} className="chip">{w}</li>
            ))}
          </ul>
        )}
        {clashes.length > 0 && (
          <p className="sch-clash">
            <TriangleAlert size={13} aria-hidden="true" />
            <span>Clashes with {clashes.join(', ')}</span>
          </p>
        )}
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
      <span className="sch-time">{timeRange(item.starts_at, item.ends_at)}</span>
      <div className="sch-body">
        <p className="sch-title">
          {pending ? (
            <Clock size={14} className="sch-title-icon" aria-hidden="true" />
          ) : (
            <Users size={14} className="sch-title-icon" aria-hidden="true" />
          )}
          {title}
        </p>
        <p className="sch-meta">
          <span>{outgoing ? 'Request sent' : pending ? 'Meeting request' : 'Meeting'}</span>
          {room && <span>{room}</span>}
          {!room && pending && <span>Place not set</span>}
        </p>
        {pending && (
          <ul className="chips sch-why">
            <li className="chip chip-warn">Pending</li>
          </ul>
        )}
      </div>
    </li>
  )
}
