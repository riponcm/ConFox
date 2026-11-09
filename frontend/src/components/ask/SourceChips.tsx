import { FileText, MapPin } from 'lucide-react'
import { citedNumbers, formatWhen, placeName, type Source } from './chat.ts'

type Props = {
  text: string
  sources: Source[]
  /** When set, chips are buttons (Catch up jumps to the transcript part); otherwise plain labels. */
  onSelect?: (source: Source) => void
}

/** The sources an answer actually cites, in the order it cites them. */
export default function SourceChips({ text, sources, onSelect }: Props) {
  const byN = new Map(sources.map((s) => [s.n, s]))
  const cited = citedNumbers(text)
    .map((n) => byN.get(n))
    .filter((s): s is Source => Boolean(s))
  if (!cited.length) return null

  return (
    <ul className="chat-sources" aria-label="Sources">
      {cited.map((s) => {
        const body = (
          <>
            <span className="chat-source-n">{s.n}</span>
            <span className="chat-source-body">
              <span className="chat-source-title">{s.title}</span>
              {s.kind === 'transcript' && (
                <span className="chat-source-meta">
                  <FileText size={12} aria-hidden="true" /> Sample transcript (generated), not the speaker&rsquo;s words
                </span>
              )}
              {s.starts_at && (
                <span className="chat-source-meta">
                  {formatWhen(s.starts_at)}
                  {s.room && (
                    <>
                      {' '}
                      <MapPin size={12} aria-hidden="true" /> {placeName(s.room)}
                    </>
                  )}
                </span>
              )}
            </span>
          </>
        )
        return (
          <li key={s.n}>
            {onSelect ? (
              <button type="button" className="chat-source" onClick={() => onSelect(s)}>
                {body}
              </button>
            ) : (
              <span className="chat-source">{body}</span>
            )}
          </li>
        )
      })}
    </ul>
  )
}
