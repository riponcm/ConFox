import SessionCard from '../SessionCard.tsx'
import AgendaButton from './AgendaButton.tsx'
import { canAdd, type ToggleAgenda } from './agenda.ts'
import { dayLabel } from './time.ts'
import type { SearchResponse } from './types.ts'

type Props = {
  data: SearchResponse
  day: string
  onPickDay: (day: string) => void
  /** Session ids on the user's agenda (from GET /api/agenda); search results do not carry it. */
  agendaIds?: Set<string>
  onToggleAgenda?: ToggleAgenda
}

export default function SearchResults({ data, day, onPickDay, agendaIds, onToggleAgenda }: Props) {
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
        <ul className="sch-list sch-results-list">
          {data.results.map((s) => (
            <li key={s.id}>
              {/* The shared SessionCard (built by FIZ55) renders search results; the day shows when it differs. */}
              <SessionCard
                session={s}
                aside={
                  <div className="sch-result-aside">
                    {s.day && s.day !== day && <span className="sch-muted">{dayLabel(s.day)}</span>}
                    {onToggleAgenda && canAdd(s) && (
                      <AgendaButton
                        title={s.title}
                        on={agendaIds?.has(s.id) ?? false}
                        onToggle={() => onToggleAgenda(s.id, agendaIds?.has(s.id) ?? false)}
                      />
                    )}
                  </div>
                }
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
