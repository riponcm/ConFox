import type { ReactNode } from 'react'

/** Plain-text answer: paragraphs, "- " list items, and [n] citations shown as small markers. */
export default function AnswerText({ text }: { text: string }) {
  const blocks: ReactNode[] = []
  let items: string[] = []
  const flush = () => {
    if (items.length) {
      blocks.push(
        <ul key={`l${blocks.length}`}>
          {items.map((t, i) => (
            <li key={i}>{withCitations(t)}</li>
          ))}
        </ul>,
      )
      items = []
    }
  }
  for (const line of text.split('\n')) {
    const item = line.match(/^\s*(?:[-*]|\d+\.)\s+(.*)$/)
    if (item) {
      items.push(item[1])
    } else {
      flush()
      if (line.trim()) blocks.push(<p key={`p${blocks.length}`}>{withCitations(line)}</p>)
    }
  }
  flush()
  return <div className="chat-answer-text">{blocks}</div>
}

function withCitations(line: string): ReactNode[] {
  return line.split(/(\[\d+\])/g).map((part, i) =>
    /^\[\d+\]$/.test(part) ? (
      <span key={i} className="chat-cite" aria-label={`source ${part.slice(1, -1)}`}>
        {part.slice(1, -1)}
      </span>
    ) : (
      part
    ),
  )
}
