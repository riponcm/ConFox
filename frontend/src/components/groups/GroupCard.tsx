import { useState } from 'react'
import { CalendarCheck, Check, Crown, LogOut, Pin, Sparkles, UserPlus, Vote } from 'lucide-react'
import { ApiError, postJSON } from '../../api.ts'
import { dayLabel, hhmm, roomLabel } from '../schedule/time.ts'
import { BASIS_ICON, BASIS_LABEL } from './fields.ts'
import type { Group, GroupSlot } from './types.ts'

type Props = {
  group: Group
  userId: string
  /** Called with the updated group after any change, and with a sentence for the live region. */
  onChanged: (group: Group, said: string) => void
}

const SHOWN_MEMBERS = 5

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  return ((parts[0]?.[0] ?? '') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
}

function when(s: GroupSlot): string {
  const room = roomLabel(s.room ?? '')
  return `${s.title} · ${dayLabel(s.starts_at.slice(0, 10))} ${hhmm(s.starts_at)}${room ? ` · ${room}` : ''}`
}

export default function GroupCard({ group: g, userId, onChanged }: Props) {
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const Icon = BASIS_ICON[g.basis]
  const headingId = `group-${g.id}`
  const maxVotes = Math.max(1, ...g.tally.map((t) => t.votes))
  const others = g.member_names.length - SHOWN_MEMBERS

  const act = async (key: string, path: string, body: unknown, said: (next: Group) => string) => {
    setBusy(key)
    setError('')
    try {
      const next = await postJSON<Group>(`groups/${encodeURIComponent(g.id)}/${path}`, body)
      onChanged(next, said(next))
    } catch (err) {
      const status = err instanceof ApiError ? err.status : 0
      setError(
        status === 409 ? 'This group just changed or is full. Reload and try again.' : 'Could not save. Try again.',
      )
    } finally {
      setBusy('')
    }
  }

  const q = `?user_id=${encodeURIComponent(userId)}`
  const join = () => act('join', `join${q}`, {}, () => `You joined ${g.title}.`)
  const leave = () => act('leave', `leave${q}`, {}, () => `You left ${g.title}.`)
  const vote = (s: GroupSlot, on: boolean) =>
    act(`vote-${s.session_id}`, 'vote', { user_id: userId, session_id: s.session_id, vote: on }, () =>
      on ? `Voted for ${s.title} at ${hhmm(s.starts_at)}.` : `Vote for ${hhmm(s.starts_at)} taken back.`,
    )
  const fix = (s: GroupSlot) =>
    act(`fix-${s.session_id}`, 'fix', { user_id: userId, session_id: s.session_id }, () =>
      `Fixed ${g.title} for ${s.title} at ${hhmm(s.starts_at)}. It is on your agenda.`,
    )

  return (
    <article className="group-card" aria-labelledby={headingId}>
      <div className="group-head">
        <h3 id={headingId} className="group-title">
          {g.title}
        </h3>
        {g.sample && (
          <span className="chip chip-warn group-sample" title="Generated sample group">
            Sample
          </span>
        )}
      </div>

      <ul className="chips group-meta" aria-label="About this group">
        <li className="chip group-basis" title={BASIS_LABEL[g.basis]}>
          <Icon size={13} aria-hidden="true" />
          <span>{g.value}</span>
        </li>
        {g.status === 'fixed' ? (
          <li className="chip group-status-fixed">Time fixed</li>
        ) : (
          <li className="chip group-status-open">Voting on a time</li>
        )}
        {g.is_host && (
          <li className="chip group-host-chip">
            <Crown size={13} aria-hidden="true" /> You host
          </li>
        )}
      </ul>

      {g.match && !g.is_member && (
        <p className="group-match">
          <Sparkles size={13} aria-hidden="true" />
          {g.match.label}
        </p>
      )}
      {g.description && <p className="group-desc">{g.description}</p>}

      <div className="group-members">
        <span className="group-avatars" aria-hidden="true">
          {g.member_names.slice(0, SHOWN_MEMBERS).map((n, i) => (
            <span key={`${g.members[i]}`} className="avatar group-avatar">
              {initials(n)}
            </span>
          ))}
          {others > 0 && <span className="avatar group-avatar group-avatar-more">+{others}</span>}
        </span>
        <span className="group-count-text">
          {g.member_count} of {g.max_members} going · hosted by {g.is_host ? 'you' : g.host_name}
        </span>
      </div>

      {g.status === 'fixed' && g.fixed_slot ? (
        <p className="group-fixed">
          <CalendarCheck size={15} aria-hidden="true" />
          <span>
            <time dateTime={g.fixed_slot.starts_at}>{when(g.fixed_slot)}</time>
            {g.is_member && ' · on your agenda'}
          </span>
        </p>
      ) : (
        <div className="group-times" role="group" aria-label={`Proposed times for ${g.title}`}>
          {g.tally.map((t) => {
            const leading = g.leading === t.session_id
            return (
              <div key={t.session_id} className={leading ? 'group-time is-leading' : 'group-time'}>
                <div className="group-time-main">
                  <time dateTime={t.starts_at} className="group-time-label">
                    {when(t)}
                  </time>
                  <span className="group-votes">
                    <span className="group-vote-bar" aria-hidden="true">
                      <span style={{ width: `${(t.votes / maxVotes) * 100}%` }} />
                    </span>
                    <span>
                      {t.votes} {t.votes === 1 ? 'vote' : 'votes'}
                      {leading && ' · leading'}
                    </span>
                  </span>
                </div>
                <div className="group-time-actions">
                  <button
                    type="button"
                    className={t.voted ? 'group-btn is-on' : 'group-btn'}
                    aria-pressed={t.voted}
                    disabled={busy !== ''}
                    onClick={() => vote(t, !t.voted)}
                    aria-label={`${t.voted ? 'Voted' : 'Vote'} for ${t.title} at ${hhmm(t.starts_at)}${g.is_member ? '' : ' (joins the group)'}`}
                  >
                    {t.voted ? <Check size={14} aria-hidden="true" /> : <Vote size={14} aria-hidden="true" />}
                    {t.voted ? 'Voted' : 'Vote'}
                  </button>
                  {g.is_host && (
                    <button
                      type="button"
                      className="group-btn group-btn-fix"
                      disabled={busy !== ''}
                      onClick={() => fix(t)}
                      aria-label={`Fix ${g.title} for ${t.title} at ${hhmm(t.starts_at)}`}
                    >
                      <Pin size={14} aria-hidden="true" />
                      Fix time
                    </button>
                  )}
                </div>
              </div>
            )
          })}
          {!g.is_member && <p className="group-hint">Voting for a time also joins the group.</p>}
        </div>
      )}

      {error && (
        <p className="meet-error" role="alert">
          {error}
        </p>
      )}

      <div className="group-actions">
        {!g.is_member && (
          <button type="button" className="btn-primary" disabled={busy !== '' || g.spots_left === 0} onClick={join}>
            <UserPlus size={15} aria-hidden="true" />
            {g.spots_left === 0 ? 'Full' : busy === 'join' ? 'Joining' : 'Join'}
          </button>
        )}
        {g.is_member && !g.is_host && (
          <button type="button" className="group-btn" disabled={busy !== ''} onClick={leave}>
            <LogOut size={14} aria-hidden="true" />
            {busy === 'leave' ? 'Leaving' : 'Leave'}
          </button>
        )}
      </div>
    </article>
  )
}
