import { fmt } from './types.ts'

type Item = { name: string; value: number }

/** Ranked horizontal bars, one series: the name above, the bar with its value at the tip below. */
export default function RankList({ items, label, unit }: { items: Item[]; label: string; unit: string }) {
  const max = Math.max(1, ...items.map((i) => i.value))
  return (
    <ol className="dash-rank" aria-label={label}>
      {items.map((item) => (
        <li key={item.name} className="dash-rank-item">
          <span className="dash-rank-name">{item.name}</span>
          <span className="dash-rank-bar-row">
            <span
              className="dash-rank-bar"
              style={{ width: `calc((100% - 44px) * ${item.value / max})` }}
              aria-hidden="true"
            />
            <span className="dash-rank-value">
              {fmt(item.value)}
              <span className="dash-sr-only"> {unit}</span>
            </span>
          </span>
        </li>
      ))}
    </ol>
  )
}
