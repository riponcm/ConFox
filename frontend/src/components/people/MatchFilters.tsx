import { X } from 'lucide-react'
import { FILTER_ICON, FILTER_LABEL, GROUP_FILTER } from './fields.ts'
import type { FilterKey, Filters, MatchResponse } from './types.ts'

type Props = {
  groups: MatchResponse['groups'] | null
  filters: Filters
  onToggle: (key: FilterKey, value: string) => void
  onClear: () => void
}

// Chips for what the user shares with others ("University of Utah · 7"), then the filters currently applied.
export default function MatchFilters({ groups, filters, onToggle, onClear }: Props) {
  const chips = GROUP_FILTER.flatMap(([group, key]) => (groups?.[group] ?? []).map((b) => ({ filter: key, value: b.key, count: b.count })),
  )
  const active = (Object.entries(filters) as [FilterKey, string | undefined][]).filter(([, v]) => v)

  return (
    <div className="match-filters">
      {chips.length > 0 && (
        <div role="group" aria-label="People who share your background">
          <p className="section-label">You share</p>
          <ul className="chips group-chips">
            {chips.map((c) => {
              const Icon = FILTER_ICON[c.filter]
              const on = filters[c.filter] === c.value
              return (
                <li key={`${c.filter}:${c.value}`}>
                  <button
                    type="button"
                    className="group-chip"
                    aria-pressed={on}
                    onClick={() => onToggle(c.filter, c.value)}
                  >
                    <Icon size={14} aria-hidden="true" />
                    <span>{c.value}</span>
                    <span className="group-count">· {c.count}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      )}
      {active.length > 0 && (
        <div className="active-filters" role="group" aria-label="Active filters">
          <ul className="chips">
            {active.map(([key, value]) => (
              <li key={key}>
                <button
                  type="button"
                  className="active-chip"
                  onClick={() => onToggle(key, value!)}
                  aria-label={`Remove filter ${FILTER_LABEL[key]}: ${value}`}
                >
                  <span>
                    {FILTER_LABEL[key]}: {value}
                  </span>
                  <X size={13} aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
          <button type="button" className="link-button" onClick={onClear}>
            Clear all
          </button>
        </div>
      )}
    </div>
  )
}
