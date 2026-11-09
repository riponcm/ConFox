import { useId, useState } from 'react'
import { type DashboardData, fmt, hhmm, hhmmFromMinutes, minutesOf, plural } from './types.ts'
import { useWidth } from './useWidth.ts'

const H = 64
const PAD_T = 6
const PAD_B = 18
const PAD_X = 4

const kindLabel = (kind: string) => kind.replace(/_/g, ' ')

/** Events per half hour as a small area with a crosshair readout, then the day's events by kind in one line. */
export default function ActivitySpark({ data }: { data: DashboardData }) {
  const { buckets, kinds, total } = data.activity
  const interval = data.timeline.interval_minutes
  const [wrapRef, width] = useWidth<HTMLDivElement>()
  const [active, setActive] = useState<number | null>(null)
  const titleId = useId()

  if (total === 0) {
    return <p className="dash-empty">No activity recorded on this day yet.</p>
  }

  const n = buckets.length
  const max = Math.max(1, ...buckets.map((b) => b.count))
  const plotH = H - PAD_T - PAD_B
  const x = (i: number) => PAD_X + (n > 1 ? (i / (n - 1)) * (width - 2 * PAD_X) : (width - 2 * PAD_X) / 2)
  const y = (v: number) => PAD_T + plotH - (v / max) * plotH
  const line = buckets.map((b, i) => `${i ? 'L' : 'M'}${x(i)},${y(b.count)}`).join('')
  const area = n ? `${line}L${x(n - 1)},${PAD_T + plotH}L${x(0)},${PAD_T + plotH}Z` : ''

  const nowMin = minutesOf(data.now)
  const endOf = (i: number) => {
    const end = minutesOf(buckets[i].start) + interval
    return data.is_today && i === n - 1 && nowMin < end ? `${hhmm(data.now)} so far` : hhmmFromMinutes(end)
  }
  const readout = (i: number) => `${plural(buckets[i].count, 'event')}, ${hhmm(buckets[i].start)} to ${endOf(i)}`

  const indexAt = (clientX: number, el: Element) => {
    const px = clientX - el.getBoundingClientRect().left - PAD_X
    const step = n > 1 ? (width - 2 * PAD_X) / (n - 1) : 1
    return Math.min(n - 1, Math.max(0, Math.round(px / step)))
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    const keys: Record<string, number> = { ArrowRight: 1, ArrowLeft: -1 }
    if (e.key in keys) {
      e.preventDefault()
      setActive((i) => Math.min(n - 1, Math.max(0, (i ?? n - 1) + keys[e.key])))
    } else if (e.key === 'Escape') {
      setActive(null)
    }
  }

  return (
    <div className="dash-spark">
      <div
        ref={wrapRef}
        className="dash-spark-plot"
        tabIndex={0}
        role="group"
        aria-label="Confox events per half hour. Use the left and right arrow keys to read each half hour."
        onKeyDown={onKeyDown}
        onFocus={() => setActive((i) => i ?? n - 1)}
        onBlur={() => setActive(null)}
        onPointerMove={(e) => n && setActive(indexAt(e.clientX, e.currentTarget))}
        onPointerLeave={() => setActive(null)}
      >
        {width > 0 && n > 0 && (
          <svg width={width} height={H} role="img" aria-labelledby={titleId}>
            <title id={titleId}>
              {`Confox events per half hour from ${hhmm(buckets[0].start)}: ${buckets.map((b) => b.count).join(', ')}`}
            </title>
            <line x1={0} x2={width} y1={PAD_T + plotH} y2={PAD_T + plotH} stroke="var(--chart-axis)" />
            <path d={area} fill="var(--accent)" fillOpacity={0.12} />
            <path d={line} fill="none" stroke="var(--accent)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
            {active !== null && (
              <>
                <line x1={x(active)} x2={x(active)} y1={PAD_T} y2={PAD_T + plotH} stroke="var(--chart-axis)" />
                <circle
                  cx={x(active)}
                  cy={y(buckets[active].count)}
                  r={4}
                  fill="var(--accent)"
                  stroke="var(--panel)"
                  strokeWidth={2}
                />
              </>
            )}
            <text x={0} y={H - 4} className="dash-tick">
              {hhmm(buckets[0].start)}
            </text>
            <text x={width} y={H - 4} textAnchor="end" className="dash-tick">
              {data.is_today ? `${hhmm(data.now)} now` : hhmmFromMinutes(minutesOf(buckets[n - 1].start) + interval)}
            </text>
          </svg>
        )}
        {active !== null && (
          <div
            className="dash-tip"
            style={{ left: Math.min(Math.max(x(active), 80), width - 80), top: -34 }}
            aria-hidden="true"
          >
            <p>
              <strong>{fmt(buckets[active].count)}</strong> {buckets[active].count === 1 ? 'event' : 'events'},{' '}
              {hhmm(buckets[active].start)}&ndash;{endOf(active).replace(' so far', '')}
            </p>
          </div>
        )}
        <p className="dash-sr-only" aria-live="polite">
          {active === null ? '' : readout(active)}
        </p>
      </div>
      <p className="dash-kinds">
        {kinds.map((k, i) => (
          <span key={k.kind}>
            {i > 0 && <span aria-hidden="true"> &middot; </span>}
            <strong className="mono">{fmt(k.count)}</strong> {kindLabel(k.kind)}
            {i < kinds.length - 1 && <span className="dash-sr-only">,</span>}
          </span>
        ))}
      </p>
    </div>
  )
}
