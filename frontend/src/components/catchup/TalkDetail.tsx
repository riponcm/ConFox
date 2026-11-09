import { ArrowLeft, LoaderCircle, MapPin, Mic } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { flushSync } from 'react-dom'
import { getJSON } from '../../api.ts'
import ChatThread from '../ask/ChatThread.tsx'
import { formatWhen, placeName, type Source } from '../ask/chat.ts'
import SampleLabel from './SampleLabel.tsx'
import type { Talk } from './TalkList.tsx'

type Detail = {
  session: Talk
  sample: boolean
  chunks: { n: number; text: string }[]
  summary: { tldr: string; takeaways: string[] }
  summary_cached: boolean
}

type Props = { id: string; onBack: () => void }

export default function TalkDetail({ id, onBack }: Props) {
  const [detail, setDetail] = useState<Detail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState(false)
  const headingRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    // The page keys this component by talk id, so a new talk starts from fresh state.
    let live = true
    getJSON<Detail>(`catchup/${encodeURIComponent(id)}`)
      .then((d) => {
        if (!live) return
        setDetail(d)
        headingRef.current?.focus()
      })
      .catch((e: Error) => live && setError(e.message))
    return () => {
      live = false
    }
  }, [id])

  function showPart(source: Source) {
    // Open the transcript first so the part has a position to scroll to.
    flushSync(() => setOpen(true))
    const el = document.getElementById(`part-${source.n}`)
    el?.focus({ preventScroll: true })
    el?.scrollIntoView({ block: 'start' })
  }

  if (error) return <p className="chat-error">Could not load this talk ({error}).</p>
  if (!detail)
    return (
      <p className="chat-thinking" aria-live="polite">
        <LoaderCircle size={16} className="chat-spin" aria-hidden="true" /> Loading the talk and its summary
      </p>
    )

  const s = detail.session
  return (
    <article className="catchup-detail" aria-labelledby="talk-title">
      <button type="button" className="catchup-back" onClick={onBack}>
        <ArrowLeft size={16} aria-hidden="true" /> All talks
      </button>
      <SampleLabel sticky />
      <h2 id="talk-title" className="catchup-title" tabIndex={-1} ref={headingRef}>
        {s.title}
      </h2>
      <p className="catchup-meta">
        {formatWhen(s.starts_at)}
        {s.ends_at && `-${s.ends_at.slice(11, 16)}`}
        <span className="catchup-place">
          <MapPin size={14} aria-hidden="true" /> {placeName(s.room)}
        </span>
      </p>
      {s.speakers.length > 0 && (
        <p className="catchup-meta">
          <Mic size={14} aria-hidden="true" /> {s.speakers.join(', ')}
        </p>
      )}

      <section className="catchup-card" aria-labelledby="tldr">
        <h3 id="tldr">TL;DR</h3>
        <p className="catchup-tldr">{detail.summary.tldr}</p>
        <h3>Three takeaways</h3>
        <ol className="catchup-takeaways">
          {detail.summary.takeaways.map((t, i) => (
            <li key={i}>{t}</li>
          ))}
        </ol>
        <p className="catchup-note">Summary written by Claude from the sample transcript.</p>
      </section>

      <details
        className="catchup-transcript"
        open={open}
        onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
      >
        <summary>
          Transcript, {detail.chunks.length} parts <span className="catchup-note">(sample, generated)</span>
        </summary>
        {detail.chunks.map((c) => (
          <section key={c.n} id={`part-${c.n}`} className="catchup-part" tabIndex={-1} aria-label={`Part ${c.n}`}>
            <p className="catchup-part-n">Part {c.n}</p>
            {c.text.split('\n\n').map((p, i) => (
              <p key={i}>{p}</p>
            ))}
          </section>
        ))}
      </details>

      <section className="catchup-ask" aria-labelledby="ask-talk">
        <h3 id="ask-talk">Ask about this talk</h3>
        <p className="catchup-note">Answers use only this transcript and cite its parts; select a part to read it.</p>
        <ChatThread
          key={id}
          endpoint={`catchup/${encodeURIComponent(id)}/ask`}
          label="Questions about this talk"
          placeholder="Ask a question about this talk"
          onSelectSource={showPart}
        />
      </section>
    </article>
  )
}
