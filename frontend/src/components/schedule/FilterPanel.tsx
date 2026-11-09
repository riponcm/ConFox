import { FACET_LABELS, FACETS, TOGGLES, type Filters, type Toggle } from './filters.ts'
import { kindLabel } from './time.ts'
import type { Bucket, DayResponse, FacetName } from './types.ts'

type Props = {
  facets: DayResponse['facets']
  filters: Filters
  onChange: (f: Filters) => void
  onClear: () => void
  onClose: () => void
}

const label = (facet: FacetName, key: string) => (facet === 'kind' ? kindLabel(key) : key)

/** Checkbox groups built from the day's own values, plus three toggles. Changes apply at once. */
export default function FilterPanel({ facets, filters, onChange, onClear, onClose }: Props) {
  const flip = (facet: FacetName, key: string) => {
    const now = filters[facet]
    onChange({ ...filters, [facet]: now.includes(key) ? now.filter((v) => v !== key) : [...now, key] })
  }
  const flipToggle = (key: Toggle) => onChange({ ...filters, [key]: !filters[key] })
  // A value chosen on another day stays listed (with 0) so it can be unticked.
  const buckets = (facet: FacetName): Bucket[] => {
    const list = facets?.[facet] ?? []
    const missing = filters[facet].filter((v) => !list.some((b) => b.key === v)).map((key) => ({ key, count: 0 }))
    return [...list, ...missing]
  }

  return (
    <div
      id="sch-filters"
      className="sch-filters"
      role="region"
      aria-label="Filters"
      onKeyDown={(e) => {
        if (e.key === 'Escape') onClose()
      }}
    >
      <div className="sch-filter-groups">
        {FACETS.map((facet) => {
          const list = buckets(facet)
          if (!list.length) return null
          return (
            <fieldset key={facet} className="sch-filter-group">
              <legend>{FACET_LABELS[facet]}</legend>
              {list.map((b) => (
                <label key={b.key} className="sch-check">
                  <input type="checkbox" checked={filters[facet].includes(b.key)} onChange={() => flip(facet, b.key)} />
                  <span className="sch-check-label">{label(facet, b.key)}</span>
                  <span className="sch-check-count">{b.count}</span>
                </label>
              ))}
            </fieldset>
          )
        })}
        <fieldset className="sch-filter-group">
          <legend>Only</legend>
          {TOGGLES.map((t) => (
            <label key={t.key} className="sch-check">
              <input type="checkbox" checked={filters[t.key]} onChange={() => flipToggle(t.key)} />
              <span className="sch-check-label">{t.label}</span>
            </label>
          ))}
        </fieldset>
      </div>
      <div className="sch-filter-foot">
        <button type="button" className="sch-ghost-btn" onClick={onClear}>
          Clear
        </button>
        <button type="button" className="btn-primary" onClick={onClose}>
          Done
        </button>
      </div>
    </div>
  )
}
