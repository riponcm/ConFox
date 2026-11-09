import { useState } from 'react'
import { Link } from 'react-router'
import { Check, Clock, Coffee, MessageSquare, Send, Undo2, X } from 'lucide-react'
import { ApiError, postJSON } from '../../api.ts'
import { hhmm, roomLabel } from '../schedule/time.ts'
import { firstName, initials, mealWord } from './types.ts'
import type { MeetingRequest, SuggestedPerson, TimelineItem } from './types.ts'

type Props = {
  meetings: TimelineItem[]
  incoming: MeetingRequest[]
  outgoing: MeetingRequest[]
  people: SuggestedPerson[]
  onChanged: () => void
}

function When({ title, startsAt, room }: { title: string; startsAt: string; room: string }) {
  return (
    <p className="brief-person-when">
      <Clock size={14} aria-hidden="true" />
      <span>
        {title} &middot; <time dateTime={startsAt}>{hhmm(startsAt)}</time>
        {room ? <> &middot; {roomLabel(room)}</> : null}
      </span>
    </p>
  )
}

function RequestCard({ req, onChanged }: { req: MeetingRequest; onChanged: () => void }) {
  const [busy, setBusy] = useState<'accept' | 'decline' | null>(null)
  const [note, setNote] = useState('')

  async function respond(action: 'accept' | 'decline') {
    setBusy(action)
    setNote('')
    try {
      await postJSON(`connect/${encodeURIComponent(req.id)}/${action}`, {})
      onChanged()
    } catch (err) {
      // The connect endpoints ship in their own pull request; until then the buttons say so instead of failing.
      setNote(err instanceof ApiError && (err.status === 404 || err.status === 405) ? 'Not available yet' : 'Could not send. Try again.')
    } finally {
      setBusy(null)
    }
  }

  return (
    <article className="brief-person brief-person-request">
      <div className="brief-person-head">
        <span className="avatar" aria-hidden="true">{initials(req.with_name)}</span>
        <div className="brief-person-id">
          <h3>{firstName(req.with_name)} wants to meet</h3>
          <p className="brief-person-sub">{req.with_name}</p>
        </div>
        <span className="brief-chip brief-chip-warn">Request</span>
      </div>
      {req.message && (
        <p className="brief-person-message">
          <MessageSquare size={14} aria-hidden="true" />
          <span>{req.message}</span>
        </p>
      )}
      <When title={req.title} startsAt={req.starts_at} room={req.room} />
      <div className="brief-person-actions">
        <button type="button" className="btn-primary" disabled={busy !== null} onClick={() => respond('accept')}>
          <Check size={15} aria-hidden="true" /> {busy === 'accept' ? 'Accepting' : 'Accept'}
        </button>
        <button type="button" className="brief-btn" disabled={busy !== null} onClick={() => respond('decline')}>
          <X size={15} aria-hidden="true" /> {busy === 'decline' ? 'Declining' : 'Decline'}
        </button>
      </div>
      {note && (
        <p className="brief-person-note" role="status">
          {note}
        </p>
      )}
    </article>
  )
}

function OutgoingCard({ req, onChanged }: { req: MeetingRequest; onChanged: () => void }) {
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')

  async function withdraw() {
    setBusy(true)
    setNote('')
    try {
      await postJSON(`connect/${encodeURIComponent(req.id)}/withdraw`, {})
      onChanged()
    } catch (err) {
      const missing = err instanceof ApiError && (err.status === 404 || err.status === 405)
      setNote(missing ? 'Not available yet' : 'Could not withdraw. Try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <article className="brief-person">
      <div className="brief-person-head">
        <span className="avatar" aria-hidden="true">{initials(req.with_name)}</span>
        <div className="brief-person-id">
          <h3>{req.with_name}</h3>
          <p className="brief-person-sub">You asked to meet</p>
        </div>
        <span className="brief-chip brief-chip-warn">Pending</span>
      </div>
      <When title={req.title} startsAt={req.starts_at} room={req.room} />
      <div className="brief-person-actions">
        <button
          type="button"
          className="brief-btn"
          disabled={busy}
          onClick={withdraw}
          aria-label={`Withdraw the request to ${req.with_name}`}
        >
          <Undo2 size={15} aria-hidden="true" /> {busy ? 'Withdrawing' : 'Withdraw'}
        </button>
      </div>
      {note && (
        <p className="brief-person-note" role="status">
          {note}
        </p>
      )}
    </article>
  )
}

export default function PeopleToday({ meetings, incoming, outgoing, people, onChanged }: Props) {
  const empty = !meetings.length && !incoming.length && !outgoing.length && !people.length
  if (empty) return <p className="brief-empty">No meetings or people to suggest today.</p>

  return (
    <ul className="brief-people" role="list">
      {meetings.map((m) => (
        <li key={m.id}>
          <article className="brief-person brief-person-meeting">
            <div className="brief-person-head">
              <span className="avatar avatar-ok" aria-hidden="true">{initials(m.with_name ?? '')}</span>
              <div className="brief-person-id">
                <h3>{m.with_name ?? 'Meeting'}</h3>
                <p className="brief-person-sub">Confirmed</p>
              </div>
              <span className="brief-chip brief-chip-ok">Meeting</span>
            </div>
            <When title={m.title} startsAt={m.starts_at} room={m.room} />
          </article>
        </li>
      ))}

      {incoming.map((r) => (
        <li key={r.id}>
          <RequestCard req={r} onChanged={onChanged} />
        </li>
      ))}

      {outgoing.map((r) => (
        <li key={r.id}>
          <OutgoingCard req={r} onChanged={onChanged} />
        </li>
      ))}

      {people.map((p) => (
        <li key={p.id}>
          <article className="brief-person">
            <div className="brief-person-head">
              <span className="avatar" aria-hidden="true">{initials(p.name)}</span>
              <div className="brief-person-id">
                <h3>{p.name}</h3>
                <p className="brief-person-sub">{[p.title, p.company].filter(Boolean).join(', ') || 'Attendee'}</p>
              </div>
              {p.sample && <span className="brief-chip">Sample</span>}
            </div>
            <p className="brief-person-when">
              <Coffee size={14} aria-hidden="true" />
              <span>
                {p.free_at ? (
                  <>
                    Free at <time dateTime={p.free_at.starts_at}>{hhmm(p.free_at.starts_at)}</time>{' '}
                    {mealWord(p.free_at.title)}
                  </>
                ) : (
                  'Suggested for you'
                )}
                {p.reason ? <> &middot; {p.reason}</> : null}
              </span>
            </p>
            <div className="brief-person-actions">
              <Link className="brief-btn" to={`/people?q=${encodeURIComponent(p.name)}`}>
                <Send size={15} aria-hidden="true" /> Meet
              </Link>
            </div>
          </article>
        </li>
      ))}
    </ul>
  )
}
