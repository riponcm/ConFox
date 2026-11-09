import { useId, useState } from 'react'
import { useWidth } from './useWidth.ts'
import { type DashboardData, type TimelineBucket, fmt, hhmm, hhmmFromMinutes, hourShort, minutesOf } from './types.ts'

const PLOT_H = 160
const TOP = 22 // room for the agenda dots and the now label
const BOTTOM = 24 // x-axis labels
const LEFT = 26 // y-axis ticks
const RIGHT = 6
const RADIUS = 4
const DOT_R = 4

/** Clean tick step so the axis shows at most four intervals. */
function niceStep(max: number): number {
  const raw = Math.max(max, 1) / 4
  const pow = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 5, 10].map((m) => m * pow).find((s) => s >= raw) ?? 10 * pow
  return Math.max(1, step)
}

/** A rectangle with the data end (top) rounded and the baseline end square. */
function topRounded(x: number, y: number, w: number, h: number, r: number): string {
  const rr = Math.min(r, w / 2, h)
  return `M${x},${y + h}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h}Z`
}

const startText = (b: TimelineBucket) =>
  `${b.total === 1 ? '1 session starts' : `${fmt(b.total)} sessions start`} at ${hhmm(b.start)}`

/** Sessions starting per half hour: one colour, past half hours lighter, the user's agenda as dots, a now line. */
export default function TimelineChart({ data }: { data: DashboardData }) {
  const { buckets, interval_minutes: interval } = data.timeline
  const [wrapRef, width] = useWidth<HTMLDivElement>()
  const [active, setActive] = useState<number | null>(null)
  const titleId = useId()
  const descId = useId()

  const n = buckets.length
  const peak = buckets.reduce((best, b) => (b.total > best.total ? b : best), buckets[0] ?? { start: '', total: 0, mine: 0 })
  const dayTotal = buckets.reduce((sum, b) => sum + b.total, 0)
  const mineTotal = buckets.reduce((sum, b) => sum + b.mine, 0)

  const step = niceStep(peak.total)
  const yMax = Math.max(step, Math.ceil(peak.total / step) * step)
  const ticks = Array.from({ length: yMax / step + 1 }, (_, i) => i * step)

  const plotW = Math.max(0, width - LEFT - RIGHT)
  const band = n ? plotW / n : 0
  const barW = Math.max(2, Math.min(24, band - 2))
  const y = (v: number) => TOP + PLOT_H - (v / yMax) * PLOT_H
  const height = TOP + PLOT_H + BOTTOM

  const first = n ? minutesOf(buckets[0].start) : 0
  const last = first + n * interval
  const xOfMinutes = (m: number) => LEFT + ((m - first) / interval) * band

  const nowMin = minutesOf(data.now)
  const showNow = data.is_today && n > 0 && nowMin >= first && nowMin <= last
  const nowX = xOfMinutes(nowMin)
  const isPast = (b: TimelineBucket) => data.is_today && (nowMin > last || minutesOf(b.start) + interval <= nowMin)

  // Even hours inside the window: 8a 10a 12p 2p 4p 6p.
  const hourTicks: number[] = []
  for (let m = Math.ceil(first / 120) * 120; m < last; m += 120) if (m > first) hourTicks.push(m)

  const indexAt = (clientX: number, el: Element) => {
    const x = clientX - el.getBoundingClientRect().left - LEFT
    return Math.min(n - 1, Math.max(0, Math.floor(x / band)))
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (!n) return
    const keys: Record<string, number> = { ArrowRight: 1, ArrowLeft: -1 }
    if (e.key in keys) {
      e.preventDefault()
      setActive((i) => Math.min(n - 1, Math.max(0, (i ?? 0) + keys[e.key])))
    } else if (e.key === 'Home' || e.key === 'End') {
      e.preventDefault()
      setActive(e.key === 'Home' ? 0 : n - 1)
    } else if (e.key === 'Escape') {
      setActive(null)
    }
  }

  const activeBucket = active === null ? null : buckets[active]
  const tipLeft = active === null ? 0 : Math.min(Math.max(LEFT + (active + 0.5) * band, 90), width - 90)
  const nowIndex = showNow ? Math.min(n - 1, Math.floor((nowMin - first) / interval)) : 0
  const readout = activeBucket
    ? `${startText(activeBucket)}${activeBucket.mine ? `, ${activeBucket.mine} on your agenda` : ''}`
    : ''

  return (
    <div className="dash-timeline">
      {(showNow || mineTotal > 0) && (
        <ul className="dash-legend" aria-label="Chart marks">
          {mineTotal > 0 && (
            <li>
              <svg width="10" height="10" aria-hidden="true">
                <circle cx="5" cy="5" r="4" fill="var(--text)" />
              </svg>
              your agenda
            </li>
          )}
          {showNow && (
            <li>
              <svg width="16" height="10" aria-hidden="true">
                <line x1="0" x2="16" y1="5" y2="5" stroke="var(--chart-now)" strokeWidth="1.5" strokeDasharray="4 3" />
              </svg>
              now
            </li>
          )}
        </ul>
      )}

      <div
        ref={wrapRef}
        className="dash-plot"
        tabIndex={0}
        role="group"
        aria-label="Sessions through the day. Use the left and right arrow keys to read each half hour."
        onKeyDown={onKeyDown}
        onFocus={() => setActive((i) => i ?? nowIndex)}
        onBlur={() => setActive(null)}
        onPointerMove={(e) => n && setActive(indexAt(e.clientX, e.currentTarget))}
        onPointerLeave={() => setActive(null)}
      >
        {width > 0 && (
          <svg width={width} height={height} role="img" aria-labelledby={`${titleId} ${descId}`}>
            <title id={titleId}>Sessions starting per half hour</title>
            <desc id={descId}>
              {`${fmt(dayTotal)} sessions start between ${hhmmFromMinutes(first)} and ${hhmmFromMinutes(last)}. `}
              {peak.total > 0 ? `The busiest half hour is ${hhmm(peak.start)} with ${fmt(peak.total)}. ` : ''}
              {mineTotal > 0 ? `${mineTotal} of your agenda items start in this window. ` : ''}
              {showNow ? `The current time is ${hhmm(data.now)}. ` : ''}
              Every value is listed in the table that follows.
            </desc>

            {ticks.map((t) => (
              <g key={t}>
                <line
                  x1={LEFT}
                  x2={width - RIGHT}
                  y1={y(t)}
                  y2={y(t)}
                  stroke={t === 0 ? 'var(--chart-axis)' : 'var(--chart-grid)'}
                />
                <text x={LEFT - 6} y={y(t)} dy="0.32em" textAnchor="end" className="dash-tick">
                  {t}
                </text>
              </g>
            ))}

            {active !== null && (
              <rect x={LEFT + active * band} y={TOP} width={band} height={PLOT_H} rx={4} fill="var(--panel-2)" />
            )}

            {buckets.map((b, i) => {
              const x = LEFT + i * band + (band - barW) / 2
              const top = y(b.total)
              return (
                <g key={b.start}>
                  {b.total > 0 && (
                    <path
                      d={topRounded(x, top, barW, TOP + PLOT_H - top, RADIUS)}
                      fill="var(--accent)"
                      fillOpacity={isPast(b) ? 0.38 : 1}
                    />
                  )}
                  {b.mine > 0 && (
                    <circle
                      cx={x + barW / 2}
                      cy={top - DOT_R - 4}
                      r={DOT_R}
                      fill="var(--text)"
                      stroke="var(--panel)"
                      strokeWidth={2}
                    />
                  )}
                </g>
              )
            })}

            {hourTicks.map((m) => (
              <text key={m} x={xOfMinutes(m)} y={TOP + PLOT_H + 16} textAnchor="middle" className="dash-tick">
                {hourShort(m)}
              </text>
            ))}

            {showNow && (
              <line
                x1={nowX}
                x2={nowX}
                y1={TOP - 14}
                y2={TOP + PLOT_H}
                stroke="var(--chart-now)"
                strokeWidth={1.5}
                strokeDasharray="4 3"
              />
            )}
          </svg>
        )}

        {activeBucket && (
          <div className="dash-tip" style={{ left: tipLeft }} aria-hidden="true">
            <p>
              <strong>{fmt(activeBucket.total)}</strong> {activeBucket.total === 1 ? 'session starts' : 'sessions start'}{' '}
              at {hhmm(activeBucket.start)}
            </p>
            {activeBucket.mine > 0 && (
              <p className="dash-tip-row">
                <svg width="8" height="8" aria-hidden="true">
                  <circle cx="4" cy="4" r="4" fill="var(--text)" />
                </svg>
                {activeBucket.mine} on your agenda
              </p>
            )}
          </div>
        )}
        <p className="dash-sr-only" aria-live="polite">
          {readout}
        </p>
      </div>

      {/* A table ignores width: 1px, so the visually hidden wrapper is a div. */}
      <div className="dash-sr-only">
        <table>
          <caption>Sessions starting per half hour</caption>
          <thead>
            <tr>
              <th scope="col">Half hour</th>
              <th scope="col">Sessions starting</th>
              <th scope="col">On your agenda</th>
            </tr>
          </thead>
          <tbody>
            {buckets.map((b) => (
              <tr key={b.start}>
                <th scope="row">{hhmm(b.start)}</th>
                <td>{b.total}</td>
                <td>{b.mine}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
