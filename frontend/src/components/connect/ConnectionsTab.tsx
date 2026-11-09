import { useCallback, useEffect, useState } from 'react'
import { CalendarCheck, Check, Clock, Inbox, LoaderCircle, MessageSquare, Send, Undo2, Users, X } from 'lucide-react'
import { getJSON, postJSON } from '../../api.ts'
import Avatar from '../people/Avatar.tsx'
import { dayLabel, hhmm, roomLabel } from '../schedule/time.ts'
import type { ConnectResponse, Meeting } from './types.ts'

type Props = { userId: string; onChanged?: () => void }
type Load = { status: 'loading' } | { status: 'failed' } | { status: 'ready'; data: ConnectResponse }
type Action = 'accept' | 'decline' | 'withdraw'

const DONE: Record<Action, string> = { accept: 'Accepted', decline: 'Declined', withdraw: 'Withdrew the request to' }

function When({ m, label }: { m: Meeting; label?: string }) {
  const room = roomLabel(m.room ?? '')
  return (
    <p className="conn-when">
      <Clock size={13} aria-hidden="true" />
      <span>
        {label ?? m.title} · {dayLabel(m.starts_at.slice(0, 10))} <time dateTime={m.starts_at}>{hhmm(m.starts_at)}</time>
        {room && ` · ${room}`}
      </span>
    </p>
  )
}

/** Meeting requests to and from the user, and confirmed meetings, from the existing /api/connect endpoints. */
export default function ConnectionsTab({ userId, onChanged }: Props) {
  const [load, setLoad] = useState<Load>({ status: 'loading' })
  const [busy, setBusy] = useState('')
  const [said, setSaid] = useState('')
  const [error, setError] = useState('')

  const reload = useCallback(
    (signal?: AbortSignal) =>
      getJSON<ConnectResponse>('connect', { user_id: userId }, { signal })
        .then((data) => setLoad({ status: 'ready', data }))
        .catch(() => !signal?.aborted && setLoad((l) => (l.status === 'ready' ? l : { status: 'failed' }))),
    [userId],
  )

  useEffect(() => {
    const ctrl = new AbortController()
    reload(ctrl.signal)
    return () => ctrl.abort()
  }, [reload])

  const act = async (m: Meeting, action: Action) => {
    setBusy(`${m.id}:${action}`)
    setError('')
    try {
      await postJSON(`connect/${encodeURIComponent(m.id)}/${action}?user_id=${encodeURIComponent(userId)}`, {})
      setSaid(`${DONE[action]} ${m.with_name}.`)
      await reload()
      onChanged?.()
    } catch {
      setError(`Could not ${action} the request from ${m.with_name}. Try again.`)
    } finally {
      setBusy('')
    }
  }

  if (load.status === 'loading')
    return (
      <p className="people-status">
        <LoaderCircle size={18} className="spin" aria-hidden="true" />
        Loading your connections…
      </p>
    )
  if (load.status === 'failed')
    return <p className="people-status">Could not load connections. Check that the API is running and try again.</p>

  const { incoming, outgoing, meetings } = load.data
  const button = (m: Meeting, action: Action, label: string, primary = false) => {
    const Icon = action === 'accept' ? Check : action === 'decline' ? X : Undo2
    const key = `${m.id}:${action}`
    return (
      <button
        type="button"
        className={primary ? 'btn-primary' : 'group-btn'}
        disabled={busy !== ''}
        onClick={() => act(m, action)}
        aria-label={`${label} ${action === 'withdraw' ? 'the request to' : 'the request from'} ${m.with_name}`}
      >
        <Icon size={14} aria-hidden="true" />
        {busy === key ? `${label}…` : label}
      </button>
    )
  }

  return (
    <div className="conn-tab">
      <p className="people-note">Sample people and their requests are generated demo data.</p>
      <p className="people-sr-only" role="status" aria-live="polite">
        {said}
      </p>
      {error && (
        <p className="meet-error" role="alert">
          {error}
        </p>
      )}

      <section aria-labelledby="conn-incoming">
        <h2 id="conn-incoming" className="section-label group-section-label">
          <Inbox size={14} aria-hidden="true" /> Requests to you · {incoming.length}
        </h2>
        {incoming.length === 0 ? (
          <p className="group-empty">No requests waiting for you.</p>
        ) : (
          <ul className="conn-list">
            {incoming.map((m) => (
              <li key={m.id}>
                <article className="conn-card" aria-labelledby={`conn-${m.id}`}>
                  <Avatar name={m.with_name} />
                  <div className="conn-body">
                    <div className="conn-head">
                      <h3 id={`conn-${m.id}`}>{m.with_name} wants to meet</h3>
                      {m.sample && <span className="chip chip-warn group-sample">Sample</span>}
                    </div>
                    <When m={m} />
                    {m.message && (
                      <p className="conn-message">
                        <MessageSquare size={13} aria-hidden="true" />
                        <span>{m.message}</span>
                      </p>
                    )}
                    <div className="group-actions">
                      {button(m, 'accept', 'Accept', true)}
                      {button(m, 'decline', 'Decline')}
                    </div>
                  </div>
                </article>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="conn-outgoing">
        <h2 id="conn-outgoing" className="section-label group-section-label">
          <Send size={14} aria-hidden="true" /> Requests you sent · {outgoing.length}
        </h2>
        {outgoing.length === 0 ? (
          <p className="group-empty">No requests waiting on others. Use Meet on a Match card to send one.</p>
        ) : (
          <ul className="conn-list">
            {outgoing.map((m) => (
              <li key={m.id}>
                <article className="conn-card" aria-labelledby={`conn-${m.id}`}>
                  <Avatar name={m.with_name} />
                  <div className="conn-body">
                    <div className="conn-head">
                      <h3 id={`conn-${m.id}`}>{m.with_name}</h3>
                      <span className="chip chip-warn">Pending</span>
                    </div>
                    <When m={m} />
                    <div className="group-actions">{button(m, 'withdraw', 'Withdraw')}</div>
                  </div>
                </article>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="conn-meetings">
        <h2 id="conn-meetings" className="section-label group-section-label">
          <CalendarCheck size={14} aria-hidden="true" /> Confirmed meetings · {meetings.length}
        </h2>
        {meetings.length === 0 ? (
          <p className="group-empty">No confirmed meetings yet.</p>
        ) : (
          <ul className="conn-list">
            {meetings.map((m) => {
              const group = Boolean(m.group_id)
              return (
                <li key={m.id}>
                  <article className="conn-card conn-card-ok" aria-labelledby={`conn-${m.id}`}>
                    {group ? (
                      <span className="avatar people-avatar conn-group-avatar" aria-hidden="true">
                        <Users size={18} />
                      </span>
                    ) : (
                      <Avatar name={m.with_name} />
                    )}
                    <div className="conn-body">
                      <div className="conn-head">
                        <h3 id={`conn-${m.id}`}>{m.with_name}</h3>
                        <span className="chip group-status-fixed">{group ? 'Group meetup' : 'Confirmed'}</span>
                        {m.sample && <span className="chip chip-warn group-sample">Sample</span>}
                      </div>
                      <When m={m} label={group ? 'Meetup' : undefined} />
                    </div>
                  </article>
                </li>
              )
            })}
          </ul>
        )}
      </section>
    </div>
  )
}
