import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import {
  ArrowLeft,
  BookOpenText,
  CalendarDays,
  CircleCheck,
  ExternalLink,
  FileText,
  MapPin,
  Sparkles,
  TriangleAlert,
  UsersRound,
  X,
} from 'lucide-react'
import { ApiError, DEMO_USER, deleteJSON, getJSON, postJSON } from '../../api.ts'
import AgendaButton from '../schedule/AgendaButton.tsx'
import KindIcon from '../schedule/KindIcon.tsx'
import { durationMin, kindLabel, longDate, roomLabel, shortDate, timeRange } from '../schedule/time.ts'
import type { SessionDetail, SessionListItem, Speaker } from './types.ts'
import '../../styles/schedule.css'
import '../../styles/session.css'

type Props = {
  /** The session shown; null when the drawer is closed. */
  sessionId: string | null
  canGoBack: boolean
  onNavigate: (sessionId: string) => void
  onBack: () => void
  onClose: () => void
  onAgendaChanged: () => void
}

type Answer = { key: string; data?: SessionDetail; failed?: boolean }

const DESCRIPTION_PREVIEW = 360

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  return ((parts[0]?.[0] ?? '') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase() || '?'
}

function goingText(going: number, names: string[]): string {
  if (!going) return 'Nobody has saved it yet'
  if (!names.length) return `${going} going`
  const others = going - names.length
  return others > 0 ? `${names.join(', ')} and ${others} more going` : `${names.join(', ')} going`
}

/** One session in a drawer list; the title opens it inside the drawer (Back returns). */
function ListRow({ item, onOpen }: { item: SessionListItem; onOpen: (id: string) => void }) {
  const room = roomLabel(item.room)
  return (
    <li className="sd-list-row">
      <button type="button" className="sd-list-btn" onClick={() => onOpen(item.id)}>
        <KindIcon kind={item.kind} isFood={item.is_food} />
        <span className="sd-list-text">
          <span className="sd-list-title">{item.title}</span>
          <span className="sd-list-meta">
            <span>
              {shortDate(item.day)}, <time dateTime={item.starts_at}>{timeRange(item.starts_at, item.ends_at)}</time>
            </span>
            {room && <span>{room}</span>}
          </span>
        </span>
        {item.on_agenda && (
          <span className="chip chip-ok sd-list-added">
            <CircleCheck size={12} aria-hidden="true" />
            Added
          </span>
        )}
      </button>
    </li>
  )
}

function SpeakerCard({ speaker, onOpen }: { speaker: Speaker; onOpen: (id: string) => void }) {
  // Public titles often end with the company already ("Product, AWS"); do not say it twice.
  const role =
    speaker.company && speaker.title.includes(speaker.company)
      ? speaker.title
      : [speaker.title, speaker.company].filter(Boolean).join(' · ')
  return (
    <li className="sd-speaker">
      <span className="avatar sd-avatar" aria-hidden="true">
        {initials(speaker.name)}
      </span>
      <div className="sd-speaker-body">
        <p className="sd-speaker-name">{speaker.name}</p>
        {role && <p className="sd-speaker-role">{role}</p>}
        {speaker.bio && <p className="sd-speaker-bio">{speaker.bio}</p>}
        {speaker.links.length > 0 && (
          <ul className="sd-links">
            {speaker.links.map((l) => (
              <li key={l.url}>
                <a href={l.url} target="_blank" rel="noopener noreferrer">
                  <ExternalLink size={12} aria-hidden="true" />
                  {l.title}
                  <span className="sd-sr-only"> (opens in a new tab)</span>
                </a>
              </li>
            ))}
          </ul>
        )}
        {speaker.other_sessions.length > 0 && (
          <div className="sd-also">
            <p className="sd-also-label">Also speaking</p>
            <ul className="sd-list">
              {speaker.other_sessions.map((s) => (
                <ListRow key={s.id} item={s} onOpen={onOpen} />
              ))}
            </ul>
          </div>
        )}
      </div>
    </li>
  )
}

function Body({
  data,
  onOpen,
  onToggle,
}: {
  data: SessionDetail
  onOpen: (id: string) => void
  onToggle: () => Promise<void>
}) {
  const s = data.session
  const [expanded, setExpanded] = useState(false)
  const description = (s.description ?? '').trim()
  const long = description.length > DESCRIPTION_PREVIEW
  const shown = long && !expanded ? `${description.slice(0, DESCRIPTION_PREVIEW).trimEnd()}…` : description
  const room = roomLabel(s.room)
  const similarTitle = data.similar.basis === 'track' ? 'Later in this track' : 'Similar sessions'
  const chips = [s.track, s.level, ...(s.projects ?? [])].filter((c): c is string => !!c)

  return (
    <>
      <div className="sd-hero">
        <p className="sd-kind">
          <KindIcon kind={s.kind} isFood={s.is_food} size={16} />
          <span>{kindLabel(s.kind, s.is_food)}</span>
        </p>
        <h2 id="session-drawer-title" className="sd-title" tabIndex={-1}>
          {s.title}
        </h2>
        <p className="sd-fact">
          <CalendarDays size={15} aria-hidden="true" />
          <span>
            <span aria-hidden="true">{shortDate(s.day)}</span>
            <span className="sd-sr-only">{longDate(s.day)}</span>,{' '}
            <time dateTime={s.starts_at}>{timeRange(s.starts_at, s.ends_at)}</time>{' '}
            <span className="sd-muted">
              &middot; <time dateTime={`PT${durationMin(s)}M`}>{durationMin(s)} min</time>
            </span>
          </span>
        </p>
        {(room || s.venue) && (
          <p className="sd-fact">
            <MapPin size={15} aria-hidden="true" />
            <span>
              {room || s.venue}
              {room && s.venue && <span className="sd-muted"> &middot; {s.venue}</span>}
            </span>
          </p>
        )}
        {chips.length > 0 && (
          <ul className="chips sd-chips" aria-label="Track, level and projects">
            {chips.map((c) => (
              <li key={c} className="chip chip-track">
                {c}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="sd-actions">
        {data.can_add && (
          <AgendaButton title={s.title} on={data.on_agenda} offLabel="Add to agenda" onToggle={onToggle} />
        )}
        {data.catch_up.available && (
          <Link className="sd-action-link" to={`/catch-up?talk=${encodeURIComponent(s.id)}`}>
            <BookOpenText size={14} aria-hidden="true" />
            Catch up on this talk
          </Link>
        )}
        {data.slides_url && (
          <a className="sd-action-link" href={data.slides_url} target="_blank" rel="noopener noreferrer">
            <FileText size={14} aria-hidden="true" />
            Slides
            <span className="sd-sr-only"> (opens in a new tab)</span>
          </a>
        )}
      </div>

      {data.clashes.length > 0 && (
        <p className="sd-clash" role="note">
          <TriangleAlert size={15} aria-hidden="true" />
          <span>Overlaps {data.clashes.join(', ')}</span>
        </p>
      )}

      <section className="sd-section" aria-labelledby="sd-why">
        <h3 id="sd-why" className="section-label">
          Why it matches you
        </h3>
        {data.why.length ? (
          <ul className="chips sd-chips">
            {data.why.map((w) => (
              <li key={w.label} className={w.kind === 'similar' ? 'chip chip-similar' : 'chip'}>
                <Sparkles size={12} aria-hidden="true" />
                {w.label}
              </li>
            ))}
          </ul>
        ) : (
          <p className="sd-muted sd-small">Nothing in your profile points here.</p>
        )}
        {data.similarity && !data.why.some((w) => w.kind === 'similar') && (
          <p className="sd-muted sd-small">{data.similarity.label}.</p>
        )}
      </section>

      <section className="sd-section" aria-labelledby="sd-going">
        <h3 id="sd-going" className="section-label">
          Going
        </h3>
        <p className="sd-going">
          <UsersRound size={15} aria-hidden="true" />
          <span>{goingText(data.going, data.going_names)}</span>
        </p>
        <p className="sample-note">From generated sample attendees.</p>
      </section>

      {description && (
        <section className="sd-section" aria-labelledby="sd-about">
          <h3 id="sd-about" className="section-label">
            About
          </h3>
          <p className="sd-description" id="sd-description">
            {shown}
          </p>
          {long && (
            <button
              type="button"
              className="sd-more"
              aria-expanded={expanded}
              aria-controls="sd-description"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? 'Show less' : 'Show more'}
            </button>
          )}
        </section>
      )}

      {data.speakers.length > 0 && (
        <section className="sd-section" aria-labelledby="sd-speakers">
          <h3 id="sd-speakers" className="section-label">
            {data.speakers.length === 1 ? 'Speaker' : `Speakers (${data.speakers.length})`}
          </h3>
          <ul className="sd-speakers">
            {data.speakers.map((sp) => (
              <SpeakerCard key={sp.id} speaker={sp} onOpen={onOpen} />
            ))}
          </ul>
        </section>
      )}

      {data.similar.items.length > 0 && (
        <section className="sd-section" aria-labelledby="sd-similar">
          <h3 id="sd-similar" className="section-label">
            {similarTitle}
          </h3>
          <ul className="sd-list">
            {data.similar.items.map((item) => (
              <ListRow key={item.id} item={item} onOpen={onOpen} />
            ))}
          </ul>
        </section>
      )}
    </>
  )
}

/**
 * The session details drawer: a native modal dialog on the right (full screen on a phone), so focus is trapped,
 * Escape closes it and focus returns to the title that opened it.
 */
export default function SessionDrawer({ sessionId, canGoBack, onNavigate, onBack, onClose, onAgendaChanged }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  const bodyRef = useRef<HTMLDivElement>(null)
  const [answer, setAnswer] = useState<Answer | null>(null)
  const [reload, setReload] = useState(0)
  const [agendaFailed, setAgendaFailed] = useState<string | null>(null)
  const open = sessionId !== null
  const key = `${sessionId}#${reload}`
  // Keep the last session on screen (dimmed) while the next loads, so Back and Similar do not flash.
  const loading = open && answer?.key !== key
  const data = answer?.data && answer.data.session.id === sessionId ? answer.data : null
  const shown = data ?? (loading ? answer?.data : undefined)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  useEffect(() => {
    if (!sessionId) return
    const ctrl = new AbortController()
    getJSON<SessionDetail>(`sessions/${encodeURIComponent(sessionId)}`, { user_id: DEMO_USER }, { signal: ctrl.signal })
      .then((d) => setAnswer({ key, data: d }))
      .catch(() => !ctrl.signal.aborted && setAnswer({ key, failed: true }))
    return () => ctrl.abort()
  }, [sessionId, key])

  // A new session in the drawer starts at the top, with focus on its title for screen readers.
  const shownId = data?.session.id
  useEffect(() => {
    if (!shownId) return
    bodyRef.current?.scrollTo({ top: 0 })
    // Back disappears on the first session, so focus would otherwise fall to the page.
    if (ref.current?.open) document.getElementById('session-drawer-title')?.focus()
  }, [shownId])

  const toggle = async () => {
    if (!data) return
    const id = data.session.id
    try {
      if (data.on_agenda) await deleteJSON(`agenda/${encodeURIComponent(id)}`, { user_id: DEMO_USER })
      else await postJSON('agenda', { user_id: DEMO_USER, session_id: id })
      setAgendaFailed(null)
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 404)) setAgendaFailed(id)
    }
    setReload((r) => r + 1)
    onAgendaChanged()
  }

  const failed = open && !loading && answer?.failed
  return (
    <dialog
      ref={ref}
      className="drawer session-drawer"
      aria-labelledby={shown ? 'session-drawer-title' : 'session-drawer-label'}
      aria-busy={loading}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) ref.current?.close()
      }}
    >
      <div className="sd-body" ref={bodyRef}>
        <div className="drawer-head sd-head">
          {canGoBack ? (
            <button type="button" className="sd-back" onClick={onBack}>
              <ArrowLeft size={16} aria-hidden="true" />
              Back
            </button>
          ) : (
            <h2 id="session-drawer-label">Session</h2>
          )}
          <button type="button" className="icon-button" aria-label="Close session details" onClick={() => ref.current?.close()}>
            <X size={18} aria-hidden="true" />
          </button>
        </div>
        {failed && (
          <p className="sd-note" role="alert">
            Could not load this session. Is the API running?
          </p>
        )}
        {!shown && loading && (
          <p className="sd-note" role="status">
            Loading the session&hellip;
          </p>
        )}
        {agendaFailed && agendaFailed === shown?.session.id && (
          <p className="sd-note sd-warn" role="alert">
            Could not change your agenda. Try again.
          </p>
        )}
        {shown && (
          <div className={loading ? 'sd-content is-loading' : 'sd-content'}>
            <Body key={shown.session.id} data={shown} onOpen={onNavigate} onToggle={toggle} />
          </div>
        )}
      </div>
    </dialog>
  )
}
