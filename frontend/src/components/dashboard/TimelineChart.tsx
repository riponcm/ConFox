import { useEffect, useId, useRef, useState } from 'react'
import { type DashboardData, GROUPS, type TimelineBucket, fmt, hhmm, hhmmFromMinutes, minutesOf } from './types.ts'

const PLOT_H = 170
const TOP = 30 // room for the now label
const BOTTOM = 26 // x-axis labels
const LEFT = 30 // y-axis ticks
const RIGHT = 8
const GAP = 2 // surface gap between stacked segments
const RADIUS = 4

/** Clean tick step so the axis shows at most five intervals. */
function niceStep(max: number): number {
  const raw = Math.max(max, 1) / 5
  const pow = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 5, 10].map((m) => m * pow).find((s) => s >= raw) ?? 10 * pow
  return Math.max(1, step)
}

/** A rectangle with the data end (top) rounded and the baseline end square. */
function topRounded(x: number, y: number, w: number, h: number, r: number): string {
  const rr = Math.min(r, w / 2, h)
  return `M${x},${y + h}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h}Z`
}

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(0)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, width] as const
}

function bucketText(b: TimelineBucket, interval: number): string {
  const start = minutesOf(b.start)
  const parts = GROUPS.filter((g) => b.counts[g.id] > 0).map((g) => `${b.counts[g.id]} ${g.label.toLowerCase()}`)
  const range = `${hhmm(b.start)} to ${hhmmFromMinutes(start + interval)}`
  return `${range}: ${b.total === 1 ? '1 session starts' : `${fmt(b.total)} sessions start`}${parts.length ? ` (${parts.join(', ')})` : ''}`
}

export default function TimelineChart({ data }: { data: DashboardData }) {
  const { buckets, interval_minutes: interval } = data.timeline
  const [wrapRef, width] = useWidth<HTMLDivElement>()
  const [active, setActive] = useState<number | null>(null)
  const titleId = useId()
  const descId = useId()

  const n = buckets.length
  const totals = GROUPS.map((g) => buckets.reduce((sum, b) => sum + b.counts[g.id], 0))
  const peakIndex = buckets.reduce((best, b, i) => (b.total > buckets[best].total ? i : best), 0)
  const peak = buckets[peakIndex]
  const dayTotal = buckets.reduce((sum, b) => sum + b.total, 0)

  const step = niceStep(peak?.total ?? 0)
  const yMax = Math.max(step, Math.ceil((peak?.total ?? 0) / step) * step)
  const ticks = Array.from({ length: yMax / step + 1 }, (_, i) => i * step)

  const plotW = Math.max(0, width - LEFT - RIGHT)
  const band = n ? plotW / n : 0
  const barW = Math.max(2, Math.min(24, band - 4))
  const y = (v: number) => TOP + PLOT_H - (v / yMax) * PLOT_H
  const height = TOP + PLOT_H + BOTTOM

  const first = n ? minutesOf(buckets[0].start) : 0
  const xOfMinutes = (m: number) => LEFT + ((m - first) / interval) * band
  const labelEvery = (width >= 560 ? 120 : 180) / interval

  const nowMin = minutesOf(data.now)
  const showNow = data.is_today && n > 0 && nowMin >= first && nowMin <= first + n * interval
  const nowX = xOfMinutes(nowMin)
  const nowLabel = `Now ${hhmm(data.now)}`
  const nowAnchor = nowX < LEFT + 40 ? 'start' : nowX > width - 40 ? 'end' : 'middle'

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

  return (
    <div className="dash-timeline">
      <ul className="dash-legend" aria-label="Session kinds">
        {GROUPS.map((g, i) => (
          <li key={g.id} className={totals[i] ? undefined : 'is-empty'}>
            <span className="dash-swatch" style={{ background: g.color }} aria-hidden="true" />
            {g.label}
            <span className="dash-legend-count">{fmt(totals[i])}</span>
          </li>
        ))}
      </ul>

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
            <title id={titleId}>Sessions starting per half hour by kind</title>
            <desc id={descId}>
              {`${fmt(dayTotal)} sessions start between ${hhmm(buckets[0]?.start ?? '')} and ${hhmmFromMinutes(first + n * interval)}. `}
              {peak && peak.total > 0 ? `The busiest half hour is ${hhmm(peak.start)} with ${fmt(peak.total)}. ` : ''}
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
                <text x={LEFT - 8} y={y(t)} dy="0.32em" textAnchor="end" className="dash-tick">
                  {t}
                </text>
              </g>
            ))}

            {active !== null && (
              <rect
                x={LEFT + active * band}
                y={TOP}
                width={band}
                height={PLOT_H}
                rx={4}
                fill="var(--panel-2)"
              />
            )}

            {buckets.map((b, i) => {
              const x = LEFT + i * band + (band - barW) / 2
              const shown = GROUPS.filter((g) => b.counts[g.id] > 0)
              let base = 0
              return (
                <g key={b.start}>
                  {shown.map((g, j) => {
                    const top = base + b.counts[g.id]
                    const y0 = y(base)
                    const y1 = y(top)
                    base = top
                    // Segments above the first give up their bottom GAP pixels to the surface gap.
                    const h = Math.max(1, y0 - y1 - (j > 0 ? GAP : 0))
                    return j === shown.length - 1 ? (
                      <path key={g.id} d={topRounded(x, y1, barW, h, RADIUS)} fill={g.color} />
                    ) : (
                      <rect key={g.id} x={x} y={y1} width={barW} height={h} fill={g.color} />
                    )
                  })}
                  {i === peakIndex && b.total > 0 && (
                    <text x={x + barW / 2} y={y(b.total) - 6} textAnchor="middle" className="dash-peak">
                      {b.total}
                    </text>
                  )}
                </g>
              )
            })}

            {buckets.map((b, i) =>
              (minutesOf(b.start) - first) % (labelEvery * interval) === 0 ? (
                <text key={b.start} x={LEFT + i * band} y={TOP + PLOT_H + 18} textAnchor={i === 0 ? 'start' : 'middle'} className="dash-tick">
                  {hhmm(b.start)}
                </text>
              ) : null,
            )}

            {showNow && (
              <g className="dash-now">
                <line x1={nowX} x2={nowX} y1={TOP - 6} y2={TOP + PLOT_H} stroke="var(--chart-now)" strokeWidth={1.5} />
                <text x={nowX} y={TOP - 12} textAnchor={nowAnchor} className="dash-now-label">
                  {nowLabel}
                </text>
              </g>
            )}
          </svg>
        )}

        {activeBucket && (
          <div className="dash-tip" style={{ left: tipLeft }} aria-hidden="true">
            <p className="dash-tip-head">
              <strong>{fmt(activeBucket.total)}</strong> starting {hhmm(activeBucket.start)} to{' '}
              {hhmmFromMinutes(minutesOf(activeBucket.start) + interval)}
            </p>
            {GROUPS.filter((g) => activeBucket.counts[g.id] > 0).map((g) => (
              <p key={g.id} className="dash-tip-row">
                <span className="dash-tip-key" style={{ background: g.color }} />
                <strong>{activeBucket.counts[g.id]}</strong> {g.label}
              </p>
            ))}
          </div>
        )}
        <p className="dash-sr-only" aria-live="polite">
          {activeBucket ? bucketText(activeBucket, interval) : ''}
        </p>
      </div>

      {/* A table ignores width: 1px, so the visually hidden wrapper is a div. */}
      <div className="dash-sr-only">
        <table>
          <caption>Sessions starting per half hour, by kind</caption>
          <thead>
            <tr>
              <th scope="col">Half hour</th>
              {GROUPS.map((g) => (
                <th key={g.id} scope="col">{g.label}</th>
              ))}
              <th scope="col">Total</th>
            </tr>
          </thead>
          <tbody>
            {buckets.map((b) => (
              <tr key={b.start}>
                <th scope="row">{hhmm(b.start)}</th>
                {GROUPS.map((g) => (
                  <td key={g.id}>{b.counts[g.id]}</td>
                ))}
                <td>{b.total}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
