import { useEffect, useState } from 'react'
import { LoaderCircle, Search, SearchX, X } from 'lucide-react'
import { DEMO_USER, getJSON } from '../api.ts'
import MatchFilters from '../components/people/MatchFilters.tsx'
import PersonCard from '../components/people/PersonCard.tsx'
import { WHY_FILTER } from '../components/people/fields.ts'
import type { FilterKey, Filters, Kind, MatchResponse, Why } from '../components/people/types.ts'
import '../styles/people.css'

const KINDS: { value: Kind; label: string }[] = [
  { value: 'attendee', label: 'Attendees' },
  { value: 'speaker', label: 'Speakers' },
]

export default function People() {
  const [kind, setKind] = useState<Kind>('attendee')
  const [text, setText] = useState('')
  const [q, setQ] = useState('')
  const [filters, setFilters] = useState<Filters>({})
  // The last response stays on screen while the next one loads, so cards and chips do not flicker.
  // `key` says which request it answered; loading is simply "the current request has not answered yet".
  const [res, setRes] = useState<{ key: string; data: MatchResponse | null; failed: boolean }>({
    key: '',
    data: null,
    failed: false,
  })
  const params = { user_id: DEMO_USER, kind, q, size: 30, ...filters }
  const key = JSON.stringify(params)
  const { data, failed } = res
  const loading = res.key !== key

  useEffect(() => {
    const t = setTimeout(() => setQ(text.trim()), 300)
    return () => clearTimeout(t)
  }, [text])

  useEffect(() => {
    const ctrl = new AbortController()
    getJSON<MatchResponse>('people/match', JSON.parse(key), { signal: ctrl.signal })
      .then((next) => setRes({ key, data: next, failed: false }))
      .catch((err: unknown) => {
        if (ctrl.signal.aborted) return
        console.error('people match failed', err)
        setRes((r) => ({ key, data: r.data, failed: true }))
      })
    return () => ctrl.abort()
  }, [key])

  const toggle = (key: FilterKey, value: string) =>
    setFilters((f) => {
      const next = { ...f }
      if (next[key] === value) delete next[key]
      else next[key] = value
      return next
    })

  const applyWhy = (w: Why) => {
    const target = WHY_FILTER[w.field]
    if (target === 'q') {
      setText(w.value)
      setQ(w.value)
    } else {
      setFilters((f) => ({ ...f, [target]: w.value }))
    }
  }

  const hasFilters = Object.values(filters).some(Boolean) || q !== ''
  const results = data?.results ?? []

  return (
    <section className="page people-page" aria-labelledby="page-title">
      <h1 id="page-title">People</h1>
      <p className="page-lead">People worth meeting, ranked by what you share. Click a reason to see everyone who shares it.</p>

      <div className="people-controls">
        <label className="people-search">
          <Search size={16} aria-hidden="true" />
          <span className="people-sr-only">Search people</span>
          <input
            type="search"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Name, company, topic…"
            autoComplete="off"
          />
          {text && (
            <button type="button" className="icon-button people-search-clear" aria-label="Clear search" onClick={() => setText('')}>
              <X size={16} aria-hidden="true" />
            </button>
          )}
        </label>

        <div className="segmented" role="tablist" aria-label="Who to show">
          {KINDS.map((k) => (
            <button
              key={k.value}
              type="button"
              role="tab"
              aria-selected={kind === k.value}
              className="segmented-option"
              onClick={() => {
                // Background filters rarely carry over (speakers have no school or city), so a tab starts clean.
                setKind(k.value)
                setFilters({})
              }}
            >
              {k.label}
            </button>
          ))}
        </div>
      </div>

      <MatchFilters groups={data?.groups ?? null} filters={filters} onToggle={toggle} onClear={() => setFilters({})} />

      {kind === 'attendee' ? (
        <p className="people-note">Attendees are generated sample profiles; real attendee data is private.</p>
      ) : (
        <p className="people-note">Speakers are public profiles from the KubeCon schedule.</p>
      )}

      <div className="people-results" aria-live="polite" aria-busy={loading}>
        {loading && !data && !failed && (
          <p className="people-status">
            <LoaderCircle size={18} className="spin" aria-hidden="true" />
            Finding your people…
          </p>
        )}
        {failed && (
          <p className="people-status">Could not load people. Check that the API is running and try again.</p>
        )}
        {!failed && data && !loading && results.length === 0 && (
          <div className="people-status people-empty">
            <SearchX size={20} aria-hidden="true" />
            <p>No one matches {hasFilters ? 'these filters' : 'yet'}.</p>
            {hasFilters && (
              <button
                type="button"
                className="link-button"
                onClick={() => {
                  setFilters({})
                  setText('')
                  setQ('')
                }}
              >
                Clear search and filters
              </button>
            )}
          </div>
        )}
        {!failed && results.length > 0 && (
          <ol className={loading ? 'people-list is-stale' : 'people-list'}>
            {results.map((p) => (
              <li key={p.id}>
                <PersonCard person={p} onWhy={applyWhy} />
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  )
}
