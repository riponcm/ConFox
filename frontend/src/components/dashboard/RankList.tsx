import { fmt, hhmm } from './types.ts'

export type RankItem = {
  name: string
  value: number
  /** Optional start time shown before the name, as "09:00 · Name". */
  time?: string
  /** A pinned row leads the list whatever its value (the host university). */
  tag?: string
}

/**
 * Ranked horizontal bars, one series: the name above, the bar with its value at the tip below.
 * `suffix` is shown after the value ("5 going"); otherwise `unit` is read out to screen readers only.
 */
export default function RankList({
  items,
  label,
  unit,
  suffix,
  empty = 'Nothing to show.',
}: {
  items: RankItem[]
  label: string
  unit: string
  suffix?: string
  empty?: string
}) {
  if (items.length === 0) return <p className="dash-empty">{empty}</p>
  const max = Math.max(1, ...items.map((i) => i.value))
  return (
    <ol className="dash-rank" aria-label={label}>
      {items.map((item) => (
        <li key={`${item.time ?? ''}${item.name}`} className="dash-rank-item">
          <span className="dash-rank-name" title={item.name}>
            {item.time && (
              <>
                <time dateTime={item.time}>{hhmm(item.time)}</time> &middot;{' '}
              </>
            )}
            {item.name}
            {item.tag && <span className="dash-rank-tag">{item.tag}</span>}
          </span>
          <span className="dash-rank-bar-row">
            <span
              className="dash-rank-bar"
              style={{ width: `calc((100% - 72px) * ${item.value / max})` }}
              aria-hidden="true"
            />
            <span className="dash-rank-value">
              {fmt(item.value)}
              {suffix ? ` ${suffix}` : <span className="dash-sr-only"> {unit}</span>}
            </span>
          </span>
        </li>
      ))}
    </ol>
  )
}
