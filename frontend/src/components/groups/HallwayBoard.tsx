import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Clock, LoaderCircle, MapPin, Megaphone, Send, Sparkles, Trash2, Users } from 'lucide-react'
import { deleteJSON, getJSON, postJSON } from '../../api.ts'
import { dayLabel, hhmm } from '../schedule/time.ts'
import { BASIS_ICON } from './fields.ts'
import type { BoardGroup, BoardPost, BoardResponse } from './types.ts'

const POST_CHARS = 140
const LENGTH_LABEL: Record<number, string> = { 30: '30 minutes', 60: '1 hour', 180: '3 hours' }

type Props = {
  userId: string
  /** Bumped by the Groups tab whenever groups change, so the feed shows them too. */
  version: number
}

type Load = { status: 'loading' } | { status: 'failed' } | { status: 'ready'; data: BoardResponse }

/** Short-lived posts ("At the Cilium booth till 15:00") and meetup groups, newest first. */
export default function HallwayBoard({ userId, version }: Props) {
  const [load, setLoad] = useState<Load>({ status: 'loading' })
  const [text, setText] = useState('')
  const [place, setPlace] = useState('')
  const [minutes, setMinutes] = useState(60)
  const [tags, setTags] = useState<string[]>([])
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [said, setSaid] = useState('')

  const reload = useCallback(
    (signal?: AbortSignal) =>
      getJSON<BoardResponse>('groups/board', { user_id: userId }, { signal })
        .then((data) => setLoad({ status: 'ready', data }))
        .catch(() => !signal?.aborted && setLoad((l) => (l.status === 'ready' ? l : { status: 'failed' }))),
    [userId],
  )

  useEffect(() => {
    const ctrl = new AbortController()
    reload(ctrl.signal)
    return () => ctrl.abort()
  }, [reload, version])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!text.trim() || busy) return
    setBusy('post')
    setError('')
    try {
      await postJSON<BoardPost>('groups/board', { user_id: userId, text: text.trim(), place: place.trim(), minutes, tags })
      setText('')
      setPlace('')
      setTags([])
      setSaid('Posted to the hallway board.')
      await reload()
    } catch {
      setError('Could not post. Try again.')
    } finally {
      setBusy('')
    }
  }

  const remove = async (p: BoardPost) => {
    setBusy(p.id)
    setError('')
    try {
      await deleteJSON(`groups/board/${encodeURIComponent(p.id)}`, { user_id: userId })
      setSaid('Post removed.')
      await reload()
    } catch {
      setError('Could not remove the post. Try again.')
    } finally {
      setBusy('')
    }
  }

  const interests = load.status === 'ready' ? load.data.interests : []
  const lengths = load.status === 'ready' ? load.data.minutes : [30, 60, 180]
  const toggleTag = (t: string) => setTags((x) => (x.includes(t) ? x.filter((y) => y !== t) : [...x, t].slice(-3)))

  return (
    <section aria-labelledby="groups-board" className="board">
      <h2 id="groups-board" className="section-label group-section-label">
        <Megaphone size={14} aria-hidden="true" /> Hallway board
      </h2>
      <p className="people-sr-only" role="status" aria-live="polite">
        {said}
      </p>

      <form className="board-form" onSubmit={submit}>
        <label className="group-field">
          <span>Where are you, what do you want to talk about?</span>
          <input
            type="text"
            value={text}
            maxLength={POST_CHARS}
            required
            placeholder="At the Cilium booth till 15:00, come talk eBPF"
            autoComplete="off"
            aria-describedby="board-count"
            onChange={(e) => setText(e.target.value)}
          />
        </label>
        <p id="board-count" className="board-count">
          {text.length} of {POST_CHARS} characters
        </p>
        <div className="group-field-row">
          <label className="group-field group-field-grow">
            <span>Place (optional)</span>
            <input type="text" value={place} maxLength={60} autoComplete="off" onChange={(e) => setPlace(e.target.value)} />
          </label>
          <label className="group-field">
            <span>Show it for</span>
            <select value={minutes} onChange={(e) => setMinutes(Number(e.target.value))}>
              {lengths.map((m) => (
                <option key={m} value={m}>
                  {LENGTH_LABEL[m] ?? `${m} minutes`}
                </option>
              ))}
            </select>
          </label>
        </div>
        {interests.length > 0 && (
          <fieldset className="board-tags">
            <legend>Tags from your interests (up to 3)</legend>
            <div className="chips">
              {interests.map((t) => (
                <label key={t} className={tags.includes(t) ? 'board-tag is-on' : 'board-tag'}>
                  <input type="checkbox" checked={tags.includes(t)} onChange={() => toggleTag(t)} />
                  {t}
                </label>
              ))}
            </div>
          </fieldset>
        )}
        {error && (
          <p className="meet-error" role="alert">
            {error}
          </p>
        )}
        <div className="group-dialog-actions">
          <button type="submit" className="btn-primary" disabled={!text.trim() || busy !== ''}>
            {busy === 'post' ? <LoaderCircle size={15} className="spin" aria-hidden="true" /> : <Send size={15} aria-hidden="true" />}
            Post
          </button>
        </div>
      </form>

      {load.status === 'loading' && (
        <p className="people-status">
          <LoaderCircle size={18} className="spin" aria-hidden="true" />
          Loading the board…
        </p>
      )}
      {load.status === 'failed' && <p className="people-status">Could not load the hallway board.</p>}
      {load.status === 'ready' && load.data.items.length === 0 && <p className="group-empty">Nothing on the board right now.</p>}
      {load.status === 'ready' && load.data.items.length > 0 && (
        <ul className="board-list">
          {load.data.items.map((item) => (
            <li key={item.id}>
              {item.kind === 'post' ? (
                <PostCard post={item} busy={busy === item.id} onRemove={() => remove(item)} />
              ) : (
                <GroupItem group={item} />
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function PostCard({ post: p, busy, onRemove }: { post: BoardPost; busy: boolean; onRemove: () => void }) {
  return (
    <article className={p.for_you ? 'board-item is-for-you' : 'board-item'} aria-label={`Post by ${p.author_name}`}>
      <div className="board-item-head">
        <span className="board-author">{p.mine ? 'You' : p.author_name}</span>
        {p.for_you && (
          <span className="chip board-for-you">
            <Sparkles size={12} aria-hidden="true" /> Matches your interests
          </span>
        )}
        {p.sample && <span className="chip chip-warn group-sample">Sample</span>}
      </div>
      <p className="board-text">{p.text}</p>
      <p className="board-meta">
        {p.place && (
          <span>
            <MapPin size={12} aria-hidden="true" /> {p.place}
          </span>
        )}
        <span>
          <Clock size={12} aria-hidden="true" /> until <time dateTime={p.expires_at}>{hhmm(p.expires_at)}</time>
        </span>
      </p>
      {p.tags.length > 0 && (
        <ul className="chips board-item-tags" aria-label="Tags">
          {p.tags.map((t) => (
            <li key={t} className={p.matching.includes(t) ? 'chip' : 'chip board-tag-plain'}>
              {t}
            </li>
          ))}
        </ul>
      )}
      {p.mine && (
        <div className="group-actions">
          <button type="button" className="group-btn" disabled={busy} onClick={onRemove}>
            <Trash2 size={14} aria-hidden="true" /> {busy ? 'Removing' : 'Remove'}
          </button>
        </div>
      )}
    </article>
  )
}

function GroupItem({ group: g }: { group: BoardGroup }) {
  const Icon = BASIS_ICON[g.basis]
  return (
    <article className={g.for_you ? 'board-item board-group is-for-you' : 'board-item board-group'} aria-label={`Meetup group ${g.title}`}>
      <div className="board-item-head">
        <Users size={14} aria-hidden="true" className="board-group-icon" />
        <span className="board-author">Meetup group by {g.author_name}</span>
        {g.sample && <span className="chip chip-warn group-sample">Sample</span>}
      </div>
      <p className="board-text">
        <a href={`#group-${g.id}`}>{g.title}</a>
      </p>
      <p className="board-meta">
        <span>
          <Icon size={12} aria-hidden="true" /> {g.value}
        </span>
        <span>{g.member_count} going</span>
        <span>
          {g.status === 'fixed' && g.fixed_slot
            ? `${g.fixed_slot.title} ${dayLabel(g.fixed_slot.starts_at.slice(0, 10))} ${hhmm(g.fixed_slot.starts_at)}`
            : 'Voting on a time'}
        </span>
        {g.is_member && <span>You are in</span>}
      </p>
    </article>
  )
}
