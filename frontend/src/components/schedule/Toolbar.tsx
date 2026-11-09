import { Search, SlidersHorizontal, X } from 'lucide-react'
import { SORTS, type From, type Sort, type View } from './filters.ts'
import { longDate, weekday } from './time.ts'

type Option<T extends string> = { key: T; label: string }

function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
  className = '',
}: {
  label: string
  options: Option<T>[]
  value: T
  onChange: (value: T) => void
  className?: string
}) {
  return (
    <div className={`sch-seg ${className}`} role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.key} type="button" aria-pressed={o.key === value} onClick={() => onChange(o.key)}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

type Props = {
  query: string
  onQuery: (q: string) => void
  view: View
  onView: (v: View) => void
  days: string[]
  day: string | null
  today: string
  onDay: (d: string) => void
  from: From
  onFrom: (f: From) => void
  filterCount: number
  filtersOpen: boolean
  onToggleFilters: () => void
  sort: Sort
  onSort: (s: Sort) => void
}

/** One row (wrapping on small screens): search, For you / Everything, days, From now / Whole day, Filters, Sort. */
export default function Toolbar(p: Props) {
  return (
    <div className="sch-bar">
      <div className="sch-search" role="search">
        <Search size={16} className="sch-search-icon" aria-hidden="true" />
        <input
          type="search"
          className="sch-search-input"
          placeholder="Search talks, e.g. cheap LLM inference on GPUs"
          aria-label="Search sessions"
          value={p.query}
          onChange={(e) => p.onQuery(e.target.value)}
        />
        {p.query && (
          <button type="button" className="icon-button sch-search-clear" aria-label="Clear search" onClick={() => p.onQuery('')}>
            <X size={16} aria-hidden="true" />
          </button>
        )}
      </div>

      <Segmented
        label="Show"
        options={[
          { key: 'foryou', label: 'For you' },
          { key: 'all', label: 'Everything' },
        ]}
        value={p.view}
        onChange={p.onView}
      />

      {p.days.length > 0 && (
        <div className="sch-seg sch-days" role="group" aria-label="Day">
          {p.days.map((d) => (
            <button
              key={d}
              type="button"
              aria-pressed={d === p.day}
              aria-label={`${longDate(d)}${d === p.today ? ', today' : ''}`}
              title={longDate(d)}
              onClick={() => p.onDay(d)}
            >
              {weekday(d)}
              {d === p.today && <span className="sch-today-dot" aria-hidden="true" />}
            </button>
          ))}
        </div>
      )}

      <Segmented
        label="Time"
        options={[
          { key: 'now', label: 'From now' },
          { key: 'day', label: 'Whole day' },
        ]}
        value={p.from}
        onChange={p.onFrom}
      />

      <button
        type="button"
        className={p.filterCount ? 'sch-filter-btn is-active' : 'sch-filter-btn'}
        aria-expanded={p.filtersOpen}
        aria-controls="sch-filters"
        onClick={p.onToggleFilters}
      >
        <SlidersHorizontal size={15} aria-hidden="true" />
        Filters
        {p.filterCount > 0 && (
          <span className="sch-badge">
            {p.filterCount}
            <span className="sch-sr-only"> active</span>
          </span>
        )}
      </button>

      <label className="sch-sort">
        <span>Sort</span>
        <select value={p.sort} onChange={(e) => p.onSort(e.target.value as Sort)}>
          {SORTS.map((s) => (
            <option key={s.key} value={s.key}>
              {s.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  )
}
