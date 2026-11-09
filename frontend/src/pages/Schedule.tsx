import { useEffect, useState } from 'react'
import { LoaderCircle, Search, X } from 'lucide-react'
import { ApiError, getJSON } from '../api.ts'
import DayView from '../components/schedule/DayView.tsx'
import SearchResults from '../components/schedule/SearchResults.tsx'
import { dayLabel } from '../components/schedule/time.ts'
import type { DayResponse, DaysResponse, Meta, SearchResponse } from '../components/schedule/types.ts'
import '../styles/schedule.css'

// Sunday holds registration and one pre-event; the guide's days start Monday.
const FIRST_DAY = '2026-11-09'
const DEBOUNCE_MS = 300

// Each answer remembers the request it belongs to; anything else is still loading. No state is set inside
// effects except from responses.
type Answer<T> = { key: string; data?: T; failed?: boolean }
type Load<T> = { status: 'loading' | 'error' } | { status: 'ready'; data: T }
type SearchState = { status: 'idle' | 'loading' | 'unavailable' } | { status: 'ready'; data: SearchResponse }

export default function Schedule() {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [days, setDays] = useState<string[]>([])
  const [day, setDay] = useState<string | null>(null)
  const [forYouOnly, setForYouOnly] = useState(true)
  const [dayAnswer, setDayAnswer] = useState<Answer<DayResponse> | null>(null)
  const [setupFailed, setSetupFailed] = useState(false)
  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  const [searchAnswer, setSearchAnswer] = useState<Answer<SearchResponse> | null>(null)
  const searchKey = `${debounced}|${day ?? ''}`

  // Who and when, plus the day tabs. Default to today if the conference is on.
  useEffect(() => {
    let live = true
    Promise.all([getJSON<Meta>('meta'), getJSON<DaysResponse>('schedule/days')])
      .then(([m, d]) => {
        if (!live) return
        const list = d.days.map((x) => x.day).filter((x) => x >= FIRST_DAY)
        setMeta(m)
        setDays(list)
        const today = m.now.slice(0, 10)
        setDay(list.includes(today) ? today : (list[0] ?? null))
      })
      .catch(() => live && setSetupFailed(true))
    return () => {
      live = false
    }
  }, [])

  useEffect(() => {
    if (!day || !meta) return
    const ctrl = new AbortController()
    getJSON<DayResponse>('schedule/day', { day, user_id: meta.user_id }, { signal: ctrl.signal })
      .then((data) => setDayAnswer({ key: day, data }))
      .catch(() => !ctrl.signal.aborted && setDayAnswer({ key: day, failed: true }))
    return () => ctrl.abort()
  }, [day, meta])

  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), DEBOUNCE_MS)
    return () => clearTimeout(t)
  }, [query])

  useEffect(() => {
    if (!debounced) return
    const key = `${debounced}|${day ?? ''}`
    const ctrl = new AbortController()
    getJSON<SearchResponse>('search', { q: debounced, day }, { signal: ctrl.signal })
      .then((data) => setSearchAnswer({ key, data }))
      .catch((err) => {
        if (ctrl.signal.aborted) return
        if (!(err instanceof ApiError && err.status === 404)) console.warn('search failed', err)
        setSearchAnswer({ key, failed: true })
      })
    return () => ctrl.abort()
  }, [debounced, day])

  const view: Load<DayResponse> = setupFailed
    ? { status: 'error' }
    : dayAnswer?.key !== day || !dayAnswer
      ? { status: 'loading' }
      : dayAnswer.data
        ? { status: 'ready', data: dayAnswer.data }
        : { status: 'error' }
  const search: SearchState = !debounced
    ? { status: 'idle' }
    : searchAnswer?.key !== searchKey || !searchAnswer
      ? { status: 'loading' }
      : searchAnswer.data
        ? { status: 'ready', data: searchAnswer.data }
        : { status: 'unavailable' }

  const showResults = debounced !== '' && (search.status === 'ready' || search.status === 'loading')
  const sessions = view.status === 'ready' ? view.data.sessions : []
  const forYouCount = sessions.filter((s) => s.for_you).length

  return (
    <section className="page sch-page" aria-labelledby="page-title">
      <h1 id="page-title">Schedule</h1>

      <div className="sch-search" role="search">
        <Search size={16} className="sch-search-icon" aria-hidden="true" />
        <input
          type="search"
          className="sch-search-input"
          placeholder="Search talks, e.g. cheap LLM inference on GPUs"
          aria-label="Search sessions"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {query && (
          <button type="button" className="icon-button sch-search-clear" aria-label="Clear search" onClick={() => setQuery('')}>
            <X size={16} aria-hidden="true" />
          </button>
        )}
      </div>
      {search.status === 'unavailable' && <p className="sch-note">Search is not available yet</p>}

      {days.length > 0 && (
        <div className="sch-days" aria-label="Day">
          {days.map((d) => (
            <button
              key={d}
              type="button"
              className="sch-day-tab"
              aria-pressed={d === day}
              onClick={() => setDay(d)}
            >
              {dayLabel(d)}
              {meta && meta.now.slice(0, 10) === d && <span className="sch-today">Today</span>}
            </button>
          ))}
        </div>
      )}

      {showResults ? (
        search.status === 'ready' ? (
          <SearchResults data={search.data} day={day ?? ''} onPickDay={setDay} />
        ) : (
          <p className="sch-note sch-searching" role="status">
            <LoaderCircle size={14} className="sch-spin" aria-hidden="true" />
            Searching&hellip;
          </p>
        )
      ) : (
        <>
          <div className="sch-toolbar">
            <div className="sch-toggle" role="group" aria-label="Show">
              <button type="button" aria-pressed={forYouOnly} onClick={() => setForYouOnly(true)}>
                For you
              </button>
              <button type="button" aria-pressed={!forYouOnly} onClick={() => setForYouOnly(false)}>
                Everything
              </button>
            </div>
            {view.status === 'ready' && (
              <p className="sch-count">
                {forYouCount} for you of {sessions.length}
                {view.data.semantic && <span className="sch-muted"> &middot; semantic</span>}
              </p>
            )}
          </div>

          {view.status === 'loading' && <p className="sch-note">Loading the schedule&hellip;</p>}
          {view.status === 'error' && <p className="sch-note">Could not load the schedule. Is the API running?</p>}
          {view.status === 'ready' && <DayView data={view.data} forYouOnly={forYouOnly} />}
          {view.status === 'ready' && (view.data.meetings.length > 0 || view.data.pending.length > 0) && (
            <p className="sample-note">Meetings and agenda items are generated sample data.</p>
          )}
        </>
      )}
    </section>
  )
}
