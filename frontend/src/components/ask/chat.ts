/**
 * Chat over Server-Sent Events, shared by Ask and Catch up. The API sends `sources`, then `delta` text chunks,
 * then `done` with usage (or `error`). Same-origin fetch, so the Dash0 SDK adds the trace header.
 */
import { ApiError, apiUrl } from '../../api.ts'

export type Source = {
  n: number
  id: string
  title: string
  starts_at: string | null
  room: string | null
  /** Ask: "session" | "person" | "chunk". Catch up still sends "transcript" for its parts. */
  kind: string | null
  chunk?: number
  /** Sessions: talk, keynote, ... */
  session_kind?: string | null
  /** People. `title` is then the job title. */
  name?: string
  company?: string | null
  sample?: boolean
}

export type Usage = {
  model: string
  input_tokens: number
  output_tokens: number
  cost_usd: number
  duration_ms: number
  stop_reason: string | null
}

export type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  usage?: Usage
  error?: string
  streaming?: boolean
}

type ChatEvent =
  | { type: 'sources'; sources: Source[] }
  | { type: 'delta'; text: string }
  | { type: 'done'; usage: Usage }
  | { type: 'error'; message: string }

export type ChatHandlers = {
  onSources: (sources: Source[]) => void
  onDelta: (text: string) => void
  onDone: (usage: Usage) => void
  onError: (message: string) => void
}

export async function streamChat(path: string, body: unknown, h: ChatHandlers, signal?: AbortSignal) {
  const r = await fetch(apiUrl(path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(body),
    signal,
  })
  if (!r.ok || !r.body) throw new ApiError(r.status, `${r.status} ${r.statusText}`)

  const reader = r.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let end = buffer.indexOf('\n\n')
    while (end !== -1) {
      const block = buffer.slice(0, end)
      buffer = buffer.slice(end + 2)
      end = buffer.indexOf('\n\n')
      for (const line of block.split('\n')) {
        if (!line.startsWith('data: ')) continue
        const e = JSON.parse(line.slice(6)) as ChatEvent
        if (e.type === 'sources') h.onSources(e.sources)
        else if (e.type === 'delta') h.onDelta(e.text)
        else if (e.type === 'done') h.onDone(e.usage)
        else if (e.type === 'error') h.onError(e.message)
      }
    }
  }
}

/** "Tue 10 Nov, 09:42" from a local schedule time without offset. */
export function formatWhen(iso: string | null | undefined): string {
  if (!iso) return ''
  const [d, t] = iso.split('T')
  const [y, m, day] = d.split('-').map(Number)
  const date = new Date(y, m - 1, day)
  const weekday = date.toLocaleDateString('en-US', { weekday: 'short' })
  const month = date.toLocaleDateString('en-US', { month: 'short' })
  return `${weekday} ${day} ${month}${t ? `, ${t.slice(0, 5)}` : ''}`
}

/** "Salt Palace, Level 1, Hall DE" from the schedule's "Salt Palace | Level 1 | Hall DE". */
export function placeName(room: string | null | undefined): string {
  return room ? room.replaceAll(' | ', ', ') : ''
}

export function formatUsage(u: Usage): string {
  const cost = u.cost_usd < 0.01 ? u.cost_usd.toFixed(4) : u.cost_usd.toFixed(3)
  return `${u.input_tokens.toLocaleString()} in, ${u.output_tokens.toLocaleString()} out tokens · $${cost} · ${(u.duration_ms / 1000).toFixed(1)} s`
}

/** Source numbers cited in an answer, in order of first mention: "[2][5]" gives [2, 5]. */
export function citedNumbers(text: string): number[] {
  const seen: number[] = []
  for (const m of text.matchAll(/\[(\d+)\]/g)) {
    const n = Number(m[1])
    if (!seen.includes(n)) seen.push(n)
  }
  return seen
}

/** "AM" from "Alice Moreno". */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  return ((parts[0]?.[0] ?? '') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
}

/** "ML Engineer · Redwood Labs", whichever parts exist. */
export function roleLine(s: Pick<Source, 'title' | 'company'>): string {
  return [s.title, s.company].filter(Boolean).join(' \u00b7 ')
}
