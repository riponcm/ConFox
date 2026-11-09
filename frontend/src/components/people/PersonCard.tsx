import { useRef, useState } from 'react'
import { Check, Coffee, Users, X } from 'lucide-react'
import MeetPanel from '../connect/MeetPanel.tsx'
import type { Meeting } from '../connect/types.ts'
import { dayLabel, hhmm } from '../schedule/time.ts'
import Avatar from './Avatar.tsx'
import { whyIcon } from './fields.ts'
import type { MatchResult, Why } from './types.ts'

type Props = {
  person: MatchResult
  onWhy: (why: Why) => void
  userId: string
  /** The user already sent this person a request that is still pending. */
  requested?: boolean
  /** A confirmed meeting with this person, if any. */
  meeting?: Meeting
  onRequested?: (meeting: Meeting) => void
}

export default function PersonCard({ person, onWhy, userId, requested = false, meeting, onRequested }: Props) {
  const role = [person.title, person.company].filter(Boolean).join(' · ')
  const [open, setOpen] = useState(false)
  const [sent, setSent] = useState<Meeting | null>(null)
  const meetRef = useRef<HTMLButtonElement>(null)
  const confirmRef = useRef<HTMLParagraphElement>(null)
  const panelId = `meet-${person.id}`
  const isRequested = requested || sent !== null

  const close = () => {
    setOpen(false)
    meetRef.current?.focus()
  }
  const onSent = (m: Meeting) => {
    setSent(m)
    setOpen(false)
    onRequested?.(m)
    // The panel is replaced by the confirmation; focus follows so screen readers hear it.
    requestAnimationFrame(() => confirmRef.current?.focus())
  }

  return (
    <article className="person-card" aria-labelledby={`person-${person.id}`}>
      <Avatar name={person.name} picture={person.picture} />
      <div className="person-body">
        <div className="person-head">
          <h2 id={`person-${person.id}`} className="person-name">{person.name}</h2>
          {person.sample && (
            <span className="chip chip-warn person-sample" title="Generated sample attendee, not a real person">
              Sample
            </span>
          )}
          {isRequested ? (
            <button type="button" className="btn-primary meet-button is-requested" disabled>
              <Check size={15} aria-hidden="true" />
              Requested
            </button>
          ) : (
            <button
              ref={meetRef}
              type="button"
              className="btn-primary meet-button"
              aria-expanded={open}
              aria-controls={open ? panelId : undefined}
              aria-label={open ? `Close meeting times with ${person.name}` : `Meet ${person.name}`}
              onClick={() => (open ? close() : setOpen(true))}
            >
              {open ? <X size={15} aria-hidden="true" /> : <Coffee size={15} aria-hidden="true" />}
              {open ? 'Close' : 'Meet'}
            </button>
          )}
        </div>
        {role && <p className="person-role">{role}</p>}
        {person.bio && <p className="person-bio">{person.bio}</p>}
        {meeting && (
          <p className="meet-confirmed">
            <Users size={13} aria-hidden="true" />
            <span>
              {meeting.title} together {dayLabel(meeting.starts_at.slice(0, 10))} at{' '}
              <time dateTime={meeting.starts_at}>{hhmm(meeting.starts_at)}</time>
            </span>
          </p>
        )}
        {person.why.length > 0 && (
          <ul className="person-why" aria-label={`Why ${person.name} matches`}>
            {person.why.map((w) => {
              const Icon = whyIcon(w.field)
              return (
                <li key={`${w.field}:${w.value}`}>
                  <button
                    type="button"
                    className="why-chip"
                    onClick={() => onWhy(w)}
                    title={w.field === 'q' ? `Search for ${w.value}` : `Show only people matching ${w.value}`}
                  >
                    <Icon size={13} aria-hidden="true" />
                    <span>{w.label}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
        {open && !isRequested && (
          <MeetPanel id={panelId} userId={userId} person={person} onSent={onSent} onClose={close} />
        )}
        {sent && (
          <p className="meet-sent" role="status" tabIndex={-1} ref={confirmRef}>
            <Check size={15} aria-hidden="true" />
            <span>
              Request sent for <time dateTime={sent.starts_at}>{hhmm(sent.starts_at)}</time> · {sent.title}
            </span>
          </p>
        )}
      </div>
    </article>
  )
}
