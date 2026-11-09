import { ArrowUp, CircleAlert, LoaderCircle, Square } from 'lucide-react'
import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import AnswerText from './AnswerText.tsx'
import { formatUsage, streamChat, type ChatMessage, type Source } from './chat.ts'
import SourceChips from './SourceChips.tsx'

type Props = {
  /** API path that streams answers, e.g. "ask" or "catchup/123/ask". */
  endpoint: string
  extraBody?: Record<string, unknown>
  label: string
  placeholder: string
  starters?: string[]
  onSelectSource?: (source: Source) => void
}

export default function ChatThread({ endpoint, extraBody, label, placeholder, starters = [], onSelectSource }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [announce, setAnnounce] = useState('')
  const abort = useRef<AbortController | null>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const inputId = useId()

  useEffect(() => () => abort.current?.abort(), [])

  const updateLast = (fn: (m: ChatMessage) => ChatMessage) =>
    setMessages((all) => [...all.slice(0, -1), fn(all[all.length - 1])])

  async function send(question: string) {
    const q = question.trim()
    if (!q || busy) return
    // Earlier turns go back to the API as plain text; failed answers are left out.
    const history = messages
      .filter((m) => !m.error && m.content)
      .map(({ role, content }) => ({ role, content }))
    const next = [...history, { role: 'user' as const, content: q }]
    setMessages((all) => [...all, { role: 'user', content: q }, { role: 'assistant', content: '', streaming: true }])
    setDraft('')
    setBusy(true)
    setAnnounce('')
    const ctrl = new AbortController()
    abort.current = ctrl
    try {
      await streamChat(
        endpoint,
        { ...extraBody, messages: next },
        {
          onSources: (sources) => updateLast((m) => ({ ...m, sources })),
          onDelta: (text) => updateLast((m) => ({ ...m, content: m.content + text })),
          onDone: (usage) => updateLast((m) => ({ ...m, usage })),
          onError: (error) => updateLast((m) => ({ ...m, error })),
        },
        ctrl.signal,
      )
      setAnnounce('Answer ready.')
    } catch (e) {
      const stopped = ctrl.signal.aborted
      updateLast((m) => ({ ...m, error: stopped ? 'Stopped.' : `The answer failed (${(e as Error).message}).` }))
      setAnnounce(stopped ? 'Stopped.' : 'The answer failed.')
    } finally {
      updateLast((m) => ({ ...m, streaming: false }))
      setBusy(false)
      abort.current = null
      inputRef.current?.focus()
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    void send(draft)
  }

  return (
    <div className="chat">
      {messages.length === 0 && starters.length > 0 && (
        <div className="chat-starters">
          <p className="section-label">Try asking</p>
          <ul>
            {starters.map((s) => (
              <li key={s}>
                <button type="button" className="chat-starter" onClick={() => void send(s)}>
                  {s}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <ol className="chat-thread" aria-label={label}>
        {messages.map((m, i) =>
          m.role === 'user' ? (
            <li key={i} className="chat-msg chat-user">
              <span className="chat-sr-only">You asked: </span>
              {m.content}
            </li>
          ) : (
            <li key={i} className="chat-msg chat-assistant" aria-busy={m.streaming}>
              <span className="chat-sr-only">Confox answered: </span>
              {m.content ? (
                <AnswerText text={m.content} />
              ) : (
                m.streaming && (
                  <p className="chat-thinking">
                    <LoaderCircle size={16} className="chat-spin" aria-hidden="true" /> Looking through the sources
                  </p>
                )
              )}
              {m.error && (
                <p className="chat-error" role="alert">
                  <CircleAlert size={16} aria-hidden="true" /> {m.error}
                </p>
              )}
              {m.usage?.stop_reason === 'refusal' && (
                <p className="chat-error">This answer was stopped by a safety check.</p>
              )}
              {!m.streaming && m.sources && (
                <SourceChips text={m.content} sources={m.sources} onSelect={onSelectSource} />
              )}
              {m.usage && <p className="chat-usage">{formatUsage(m.usage)}</p>}
            </li>
          ),
        )}
      </ol>
      <p className="chat-sr-only" aria-live="polite">
        {announce}
      </p>

      <form className="chat-form" onSubmit={onSubmit}>
        <label className="chat-sr-only" htmlFor={inputId}>
          {placeholder}
        </label>
        <textarea
          id={inputId}
          ref={inputRef}
          className="chat-input"
          rows={2}
          value={draft}
          placeholder={placeholder}
          maxLength={2000}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              void send(draft)
            }
          }}
        />
        {busy ? (
          <button type="button" className="chat-send" onClick={() => abort.current?.abort()} aria-label="Stop answer">
            <Square size={16} aria-hidden="true" />
          </button>
        ) : (
          <button type="submit" className="chat-send" disabled={!draft.trim()} aria-label="Send question">
            <ArrowUp size={18} aria-hidden="true" />
          </button>
        )}
      </form>
    </div>
  )
}
