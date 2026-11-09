import { ScheduleRow } from './ScheduleRow.tsx'
import { dayLabel } from './time.ts'
import type { SearchResponse } from './types.ts'

type Props = { data: SearchResponse; day: string; onPickDay: (day: string) => void }

export default function SearchResults({ data, day, onPickDay }: Props) {
  const days = (data.facets?.day ?? []).filter((b) => b.count > 0)
  return (
    <section className="sch-results" aria-label="Search results">
      <p className="sch-results-head">
        <span>
          {data.total} {data.total === 1 ? 'result' : 'results'}
        </span>
        <span className="sch-muted">
          {data.mode} &middot; {Math.round(data.took_ms)} ms
        </span>
      </p>
      {days.length > 1 && (
        <ul className="chips sch-facets" aria-label="Results by day">
          {days.map((b) => (
            <li key={b.key}>
              <button
                type="button"
                className={b.key === day ? 'sch-facet is-active' : 'sch-facet'}
                aria-pressed={b.key === day}
                onClick={() => onPickDay(b.key)}
              >
                {dayLabel(b.key)} <span className="sch-muted">{b.count}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {data.results.length === 0 ? (
        <p className="sch-empty">No sessions match. Try other words.</p>
      ) : (
        <ul className="sch-list">
          {data.results.map((s) => (
            <ScheduleRow key={s.id} session={s} showDay={s.day && s.day !== day ? dayLabel(s.day) : undefined} />
          ))}
        </ul>
      )}
    </section>
  )
}
