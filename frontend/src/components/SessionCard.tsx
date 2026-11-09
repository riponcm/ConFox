import type { ReactNode } from 'react'
import { Clock, MapPin, Users } from 'lucide-react'

import type { Session, SessionKind } from '../types.ts'

type Props = {
  session: Session
  onSelect?: (session: Session) => void
  aside?: ReactNode
}

const kindLabels: Record<SessionKind, string> = {
  keynote: 'Keynote',
  talk: 'Talk',
  lightning: 'Lightning',
  tutorial: 'Tutorial',
  contribfest: 'Contribfest',
  poster: 'Poster',
  showcase: 'Showcase',
  colocated: 'Co-located',
  break: 'Break',
  registration: 'Registration',
}

function timePart(value: string) {
  return value.slice(11, 16)
}

function roomWithoutVenue(session: Session) {
  const prefix = `${session.venue} | `
  return session.room.startsWith(prefix) ? session.room.slice(prefix.length) : session.room
}

function speakers(names: string[]) {
  const shown = names.slice(0, 2).join(', ')
  const remainder = names.length - 2
  return remainder > 0 ? `${shown} +${remainder}` : shown
}

export default function SessionCard({ session, onSelect, aside }: Props) {
  const label = session.kind === 'break' && session.is_food ? 'Food' : kindLabels[session.kind]
  const badgeClass = session.kind === 'break' && session.is_food
    ? 'session-card-badge session-card-badge-food'
    : session.kind === 'keynote'
      ? 'session-card-badge session-card-badge-keynote'
      : 'session-card-badge'
  const content = (
    <>
      <div className="session-card-main">
        <div className="session-card-meta">
          <Clock size={15} aria-hidden="true" />
          <time dateTime={session.starts_at}>{timePart(session.starts_at)}–{timePart(session.ends_at)}</time>
          {session.minutes >= 60 && <span>· {session.minutes / 60 >= 2 ? `${Math.floor(session.minutes / 60)} h ${session.minutes % 60} min` : `${session.minutes} min`}</span>}
        </div>
        <h2 className="session-card-title">{session.title}</h2>
        <span className={badgeClass}>{label}</span>
        <p className="session-card-detail">
          <MapPin size={15} aria-hidden="true" />
          <span>{roomWithoutVenue(session)}</span>
        </p>
        {session.speaker_names.length > 0 && (
          <p className="session-card-detail">
            <Users size={15} aria-hidden="true" />
            <span>{speakers(session.speaker_names)}</span>
          </p>
        )}
        {session.track && <p className="session-card-track">{session.track}</p>}
      </div>
      {aside && <div className="session-card-aside">{aside}</div>}
    </>
  )

  if (onSelect) {
    return (
      <button type="button" className="session-card session-card-button" onClick={() => onSelect(session)}>
        {content}
      </button>
    )
  }

  return <article className="session-card">{content}</article>
}
