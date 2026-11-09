import { useRef, useState } from 'react'
import { Check, Coffee, Undo2, Users, X } from 'lucide-react'
import { postJSON } from '../../api.ts'
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
  /** A request the user sent this person that is still pending, if any. */
  request?: Meeting
  /** A confirmed meeting with this person, if any. */
  meeting?: Meeting
  onRequested?: (meeting: Meeting) => void
  onWithdrawn?: (personId: string) => void
}

export default function PersonCard({ person, onWhy, userId, request, meeting, onRequested, onWithdrawn }: Props) {
  const role = [person.title, person.company].filter(Boolean).join(' · ')
  const [open, setOpen] = useState(false)
  const [sent, setSent] = useState<Meeting | null>(null)
  const meetRef = useRef<HTMLButtonElement>(null)
  const confirmRef = useRef<HTMLParagraphElement>(null)
  const panelId = `meet-${person.id}`
  const pending = sent ?? request ?? null
  const isRequested = pending !== null
  const [withdrawing, setWithdrawing] = useState(false)
  const [withdrawFailed, setWithdrawFailed] = useState(false)

  const withdraw = async () => {
    if (!pending) return
    setWithdrawing(true)
    setWithdrawFailed(false)
    try {
      await postJSON(`connect/${encodeURIComponent(pending.id)}/withdraw?user_id=${encodeURIComponent(userId)}`, {})
      setSent(null)
      onWithdrawn?.(person.id)
      requestAnimationFrame(() => meetRef.current?.focus())
    } catch {
      setWithdrawFailed(true)
    } finally {
      setWithdrawing(false)
    }
  }

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
            <span className="meet-requested">
              <button type="button" className="btn-primary meet-button is-requested" disabled>
                <Check size={15} aria-hidden="true" />
                Requested
              </button>
              <button
                type="button"
                className="meet-withdraw"
                onClick={withdraw}
                disabled={withdrawing}
                aria-label={`Withdraw the request to ${person.name}`}
              >
                <Undo2 size={13} aria-hidden="true" />
                {withdrawing ? 'Withdrawing' : 'Withdraw'}
              </button>
            </span>
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
            {meeting.sample && (
              <span className="chip chip-warn meet-sample" title="Generated sample meeting">
                Sample
              </span>
            )}
          </p>
        )}
        {withdrawFailed && (
          <p className="meet-error" role="alert">
            Could not withdraw the request. Try again.
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
