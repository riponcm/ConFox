import { useEffect, useRef, useState, type FormEvent } from 'react'
import { LoaderCircle, Plus, X } from 'lucide-react'
import { ApiError, getJSON, postJSON } from '../../api.ts'
import SlotList from '../connect/SlotList.tsx'
import type { Slot } from '../connect/types.ts'
import { BASES, BASIS_LABEL, defaultTitle } from './fields.ts'
import type { Basis, Group, ProposeSeed, SlotsResponse } from './types.ts'

const MAX_TIMES = 3
const TITLE_CHARS = 80
const DESCRIPTION_CHARS = 280

type Props = {
  userId: string
  /** The open dialog's starting values; null keeps it closed. */
  seed: ProposeSeed | null
  onClose: () => void
  onCreated: (group: Group) => void
}

type Load = { status: 'loading' } | { status: 'failed' } | { status: 'ready'; slots: Slot[] }

/** Propose a meetup: who it is for, a title, an optional line, and up to three free breaks to vote on. */
export default function ProposeDialog({ userId, seed, onClose, onCreated }: Props) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (seed && !dialog.open) dialog.showModal()
    if (!seed && dialog.open) dialog.close()
  }, [seed])

  return (
    <dialog
      ref={ref}
      className="group-dialog"
      aria-labelledby="propose-title"
      onClose={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) ref.current?.close() // backdrop click
      }}
    >
      {/* Remounting per seed resets the form each time the dialog opens. */}
      {seed && (
        <ProposeForm
          key={`${seed.basis}:${seed.value}`}
          userId={userId}
          seed={seed}
          onCancel={() => ref.current?.close()}
          onCreated={onCreated}
        />
      )}
    </dialog>
  )
}

function ProposeForm({
  userId,
  seed,
  onCancel,
  onCreated,
}: {
  userId: string
  seed: ProposeSeed
  onCancel: () => void
  onCreated: (group: Group) => void
}) {
  const [basis, setBasis] = useState<Basis>(seed.basis)
  const [value, setValue] = useState(seed.value)
  const [title, setTitle] = useState(seed.title ?? (seed.value ? defaultTitle(seed.basis, seed.value) : ''))
  const [titleEdited, setTitleEdited] = useState(Boolean(seed.title))
  const [description, setDescription] = useState('')
  const [load, setLoad] = useState<Load>({ status: 'loading' })
  const [times, setTimes] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const titleRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const ctrl = new AbortController()
    getJSON<SlotsResponse>('groups/slots', { user_id: userId }, { signal: ctrl.signal })
      .then((r) => {
        setTimes(r.slots.slice(0, 1).map((s) => s.session_id))
        setLoad({ status: 'ready', slots: r.slots })
      })
      .catch(() => !ctrl.signal.aborted && setLoad({ status: 'failed' }))
    return () => ctrl.abort()
  }, [userId])

  useEffect(() => titleRef.current?.focus(), [])

  // The title follows basis and value until the user types their own.
  const retitle = (b: Basis, v: string) => {
    if (!titleEdited) setTitle(v.trim() ? defaultTitle(b, v.trim()) : '')
  }

  const toggleTime = (id: string) =>
    setTimes((t) => (t.includes(id) ? t.filter((x) => x !== id) : t.length < MAX_TIMES ? [...t, id] : t))

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (saving || !value.trim() || times.length === 0) return
    setSaving(true)
    setError('')
    try {
      const group = await postJSON<Group>('groups', {
        user_id: userId,
        basis,
        value: value.trim(),
        title: title.trim(),
        description: description.trim(),
        session_ids: times,
      })
      onCreated(group)
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 422
          ? 'One of those times is no longer free for you. Pick again.'
          : 'Could not create the meetup. Try again.',
      )
      setSaving(false)
    }
  }

  return (
    <form className="group-dialog-body" onSubmit={submit}>
      <div className="group-dialog-head">
        <h2 id="propose-title">Propose a meetup</h2>
        <button type="button" className="icon-button" aria-label="Close" onClick={onCancel}>
          <X size={18} aria-hidden="true" />
        </button>
      </div>

      <div className="group-field-row">
        <label className="group-field">
          <span>For people who share a</span>
          <select
            value={basis}
            onChange={(e) => {
              const b = e.target.value as Basis
              setBasis(b)
              retitle(b, value)
            }}
          >
            {BASES.map((b) => (
              <option key={b} value={b}>
                {BASIS_LABEL[b]}
              </option>
            ))}
          </select>
        </label>
        <label className="group-field group-field-grow">
          <span>{BASIS_LABEL[basis]}</span>
          <input
            type="text"
            required
            maxLength={TITLE_CHARS}
            value={value}
            autoComplete="off"
            onChange={(e) => {
              setValue(e.target.value)
              retitle(basis, e.target.value)
            }}
          />
        </label>
      </div>

      <label className="group-field">
        <span>Title</span>
        <input
          ref={titleRef}
          type="text"
          required
          maxLength={TITLE_CHARS}
          value={title}
          autoComplete="off"
          onChange={(e) => {
            setTitle(e.target.value)
            setTitleEdited(true)
          }}
        />
      </label>

      <label className="group-field">
        <span>Description (optional)</span>
        <textarea
          rows={2}
          maxLength={DESCRIPTION_CHARS}
          value={description}
          placeholder="Who it is for and what you will talk about"
          onChange={(e) => setDescription(e.target.value)}
        />
      </label>

      {load.status === 'loading' && (
        <p className="meet-status" role="status">
          <LoaderCircle size={15} className="spin" aria-hidden="true" />
          Finding breaks you are free for&hellip;
        </p>
      )}
      {load.status === 'failed' && (
        <p className="meet-status" role="alert">
          Could not load your free breaks. Try again later.
        </p>
      )}
      {load.status === 'ready' && load.slots.length === 0 && (
        <p className="meet-status" role="status">
          You have no free food or coffee break today or on the next conference day.
        </p>
      )}
      {load.status === 'ready' && load.slots.length > 0 && (
        <SlotList
          name="propose-times"
          legend="Times people can vote on"
          hint={`Pick up to ${MAX_TIMES} breaks you are free for. ${times.length} of ${MAX_TIMES} chosen.`}
          slots={load.slots}
          selected={times}
          max={MAX_TIMES}
          onSelect={toggleTime}
        />
      )}

      {error && (
        <p className="meet-error" role="alert">
          {error}
        </p>
      )}

      <div className="group-dialog-actions">
        <button type="button" className="group-btn" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="btn-primary" disabled={saving || !value.trim() || times.length === 0}>
          {saving ? <LoaderCircle size={15} className="spin" aria-hidden="true" /> : <Plus size={15} aria-hidden="true" />}
          Create
        </button>
      </div>
    </form>
  )
}
