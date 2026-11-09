import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { LoaderCircle, Send } from 'lucide-react'
import { ApiError, getJSON, postJSON } from '../../api.ts'
import SlotList from './SlotList.tsx'
import type { Meeting, SlotsResponse } from './types.ts'

type Props = {
  id: string
  userId: string
  person: { id: string; name: string }
  onSent: (meeting: Meeting) => void
  onClose: () => void
}

type Load = { status: 'loading' } | { status: 'failed' } | { status: 'ready'; slots: SlotsResponse['slots'] }

const MESSAGE_CHARS = 200

/** The inline Meet form: breaks both people are free for, an optional line, and Send request. */
export default function MeetPanel({ id, userId, person, onSent, onClose }: Props) {
  const first = person.name.trim().split(/\s+/)[0] || person.name
  const [load, setLoad] = useState<Load>({ status: 'loading' })
  const [selected, setSelected] = useState('')
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const checkedRef = useRef<HTMLInputElement>(null)
  const statusRef = useRef<HTMLParagraphElement>(null)

  useEffect(() => {
    const ctrl = new AbortController()
    getJSON<SlotsResponse>('connect/slots', { user_id: userId, with_id: person.id }, { signal: ctrl.signal })
      .then((r) => {
        setSelected(r.slots[0]?.session_id ?? '')
        setLoad({ status: 'ready', slots: r.slots })
      })
      .catch(() => !ctrl.signal.aborted && setLoad({ status: 'failed' }))
    return () => ctrl.abort()
  }, [userId, person.id])

  // Once the slots are in, focus goes to the chosen slot; with none, to the message saying so.
  useEffect(() => {
    if (load.status === 'loading') return
    if (checkedRef.current) checkedRef.current.focus()
    else statusRef.current?.focus()
  }, [load.status])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!selected || sending) return
    setSending(true)
    setError('')
    try {
      const meeting = await postJSON<Meeting>('connect', {
        user_id: userId,
        with_id: person.id,
        session_id: selected,
        message: message.trim(),
      })
      onSent(meeting)
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 409
          ? `You already have a meeting with ${first} at that time. Pick another slot.`
          : 'Could not send the request. Try again.',
      )
      setSending(false)
    }
  }

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.stopPropagation()
      onClose()
    }
  }

  return (
    <div id={id} className="meet-panel" onKeyDown={onKeyDown}>
      {load.status === 'loading' && (
        <p className="meet-status" role="status">
          <LoaderCircle size={15} className="spin" aria-hidden="true" />
          Finding times you are both free&hellip;
        </p>
      )}
      {load.status === 'failed' && (
        <p className="meet-status" role="alert" tabIndex={-1} ref={statusRef}>
          Could not load free times. Try again later.
        </p>
      )}
      {load.status === 'ready' && load.slots.length === 0 && (
        <p className="meet-status" role="status" tabIndex={-1} ref={statusRef}>
          You and {first} have no free break in common today or on the next conference day.
        </p>
      )}
      {load.status === 'ready' && load.slots.length > 0 && (
        <form className="meet-form" onSubmit={submit}>
          <SlotList
            name={`${id}-slot`}
            legend={`You and ${first} are both free at:`}
            slots={load.slots}
            selected={selected}
            onSelect={setSelected}
            checkedRef={checkedRef}
          />
          <label className="meet-message">
            <span className="meet-message-label">Add a line (optional)</span>
            <input
              type="text"
              value={message}
              maxLength={MESSAGE_CHARS}
              placeholder={`Hi ${first}, want to grab a coffee?`}
              autoComplete="off"
              onChange={(e) => setMessage(e.target.value)}
            />
          </label>
          {error && (
            <p className="meet-error" role="alert">
              {error}
            </p>
          )}
          <div className="meet-actions">
            <button type="submit" className="btn-primary" disabled={!selected || sending}>
              {sending ? (
                <LoaderCircle size={15} className="spin" aria-hidden="true" />
              ) : (
                <Send size={15} aria-hidden="true" />
              )}
              Send request
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
