import { useEffect, useState } from 'react'
import { LoaderCircle } from 'lucide-react'
import { useSearchParams } from 'react-router'
import { ApiError, deleteJSON, getJSON, postJSON } from '../api.ts'
import { useOpenProfile } from '../components/shellContext.ts'
import { useAgendaVersion } from '../components/session/context.ts'
import DayView from '../components/schedule/DayView.tsx'
import FilterPanel from '../components/schedule/FilterPanel.tsx'
import InterestChips from '../components/schedule/InterestChips.tsx'
import SearchResults from '../components/schedule/SearchResults.tsx'
import Toolbar from '../components/schedule/Toolbar.tsx'
import { shortDate } from '../components/schedule/time.ts'
import type { ToggleAgenda } from '../components/schedule/agenda.ts'
import {
  anyFilter,
  applyFilters,
  NO_FILTERS,
  panelCount,
  parseState,
  toParams,
  type Filters,
  type ScheduleState,
} from '../components/schedule/filters.ts'
import type {
  AgendaResponse,
  DayResponse,
  DaysResponse,
  Meta,
  SearchResponse,
} from '../components/schedule/types.ts'
import '../styles/schedule.css'
import { useProfileVersion } from '../profile.ts'

// Sunday holds registration and one pre-event; the guide's days start Monday.
const FIRST_DAY = '2026-11-09'
const DEBOUNCE_MS = 300

// Each answer remembers the request it belongs to; anything else is still loading. No state is set inside
// effects except from responses (and the debounced search text, which goes to the URL).
type Answer<T> = { key: string; data?: T; failed?: boolean }
type Load<T> = { status: 'loading' | 'error' | 'empty' } | { status: 'ready'; data: T }
type SearchState = { status: 'idle' | 'loading' | 'unavailable' } | { status: 'ready'; data: SearchResponse }

async function loadAgendaIds(userId: string, signal?: AbortSignal): Promise<Set<string>> {
  const agenda = await getJSON<AgendaResponse>('agenda', { user_id: userId }, { signal })
  return new Set(agenda.items.flatMap((i) => (i.kind === 'session' && i.session_id ? [i.session_id] : [])))
}

export default function Schedule() {
  const [params, setParams] = useSearchParams()
  const state = parseState(params)
  // Rebuilding the query string must keep the session drawer's ?session= so an open drawer stays open.
  const withSession = (prev: URLSearchParams, next: URLSearchParams) => {
    const session = prev.get('session')
    if (session) next.set('session', session)
    return next
  }
  const update = (change: Partial<ScheduleState>) =>
    setParams((prev) => withSession(prev, toParams({ ...parseState(prev), ...change })), { replace: true })
  const setFilters = (filters: Filters) => update({ filters })
  const openProfile = useOpenProfile()
  // Bumped when the session drawer changes the agenda: reload the day and the agenda ids.
  const agendaVersion = useAgendaVersion()
  // For you follows the saved profile; a save bumps the version and the day reloads.
  const profileVersion = useProfileVersion()

  const [meta, setMeta] = useState<Meta | null>(null)
  const [days, setDays] = useState<string[]>([])
  const [dayAnswer, setDayAnswer] = useState<Answer<DayResponse> | null>(null)
  const [setupFailed, setSetupFailed] = useState(false)
  const [noDays, setNoDays] = useState(false)
  const [filtersOpen, setFiltersOpen] = useState(false)
  // The box updates at once; the URL (and so the search) follows after a pause in typing.
  const [query, setQuery] = useState(state.q)
  const debounced = state.q
  const [searchAnswer, setSearchAnswer] = useState<Answer<SearchResponse> | null>(null)
  // Session ids on the agenda, for search results (the day view gets `on_agenda` from the API).
  const [agendaIds, setAgendaIds] = useState<Set<string>>(new Set())
  const [agendaFailed, setAgendaFailed] = useState(false)

  const today = meta?.now.slice(0, 10) ?? ''
  // The URL's day when it is one of the conference days; else today if the conference is on, else the first day.
  const day = state.day && days.includes(state.day) ? state.day : days.includes(today) ? today : (days[0] ?? null)
  // From now applies to today only; on other days the whole day is shown and the toggle is hidden.
  const from = day === today ? (state.from ?? 'now') : 'day'
  const searchKey = `${debounced}|${day ?? ''}`

  useEffect(() => {
    let live = true
    Promise.all([getJSON<Meta>('meta'), getJSON<DaysResponse>('schedule/days')])
      .then(([m, d]) => {
        if (!live) return
        const list = d.days.map((x) => x.day).filter((x) => x >= FIRST_DAY)
        setMeta(m)
        setDays(list)
        setNoDays(list.length === 0)
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
  }, [day, meta, agendaVersion, profileVersion])

  useEffect(() => {
    if (!meta) return
    const ctrl = new AbortController()
    loadAgendaIds(meta.user_id, ctrl.signal)
      .then(setAgendaIds)
      .catch(() => !ctrl.signal.aborted && setAgendaIds(new Set()))
    return () => ctrl.abort()
  }, [meta, agendaVersion])

  // Add or remove, then reload the day and the agenda ids so For you, clashes and the buttons agree.
  const toggleAgenda: ToggleAgenda = async (sessionId, on) => {
    if (!meta) return
    const user_id = meta.user_id
    try {
      if (on) await deleteJSON(`agenda/${encodeURIComponent(sessionId)}`, { user_id })
      else await postJSON('agenda', { user_id, session_id: sessionId })
      setAgendaFailed(false)
    } catch (err) {
      // A 404 on remove means it was already gone; the reload below shows the truth either way.
      if (!(err instanceof ApiError && err.status === 404)) {
        console.warn('agenda change failed', err)
        setAgendaFailed(true)
      }
    }
    const shown = day
    const [ids, data] = await Promise.all([
      loadAgendaIds(user_id).catch(() => null),
      shown ? getJSON<DayResponse>('schedule/day', { day: shown, user_id }).catch(() => null) : null,
    ])
    if (ids) setAgendaIds(ids)
    // Only replace the answer for the day it belongs to; a day switch in the meantime has its own request.
    if (data && shown) setDayAnswer((prev) => (prev?.key === shown ? { key: shown, data } : prev))
  }

  useEffect(() => {
    const q = query.trim()
    if (q === debounced) return
    const t = setTimeout(
      () => setParams((prev) => withSession(prev, toParams({ ...parseState(prev), q })), { replace: true }),
      DEBOUNCE_MS,
    )
    return () => clearTimeout(t)
  }, [query, debounced, setParams])

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
    : noDays
      ? { status: 'empty' }
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
  const data = view.status === 'ready' ? view.data : null
  const filters = state.filters
  const filtered = data ? applyFilters(data, filters, from === 'now' && day === today) : null
  const narrowed = anyFilter(filters) || (from === 'now' && day === today)
  const summary = data?.summary ?? {
    for_you: data?.sessions.filter((s) => s.for_you).length ?? 0,
    total: data?.sessions.length ?? 0,
    on_agenda: data?.sessions.filter((s) => s.on_agenda).length ?? 0,
  }
  const shownCount = filtered
    ? filtered.sessions.filter((s) => state.view === 'all' || s.for_you).length
    : 0
  const toggleTopic = (topic: string) =>
    setFilters({
      ...filters,
      topics: filters.topics.includes(topic) ? filters.topics.filter((t) => t !== topic) : [...filters.topics, topic],
    })

  return (
    <section className="page sch-page" aria-labelledby="page-title">
      <div className="sch-head">
        <h1 id="page-title">Schedule</h1>
        {day && data && (
          <p className="sch-summary">
            <time dateTime={day}>{shortDate(day)}</time>
            <span>
              {summary.for_you} of {summary.total} for you
            </span>
            <span>{summary.on_agenda} on your agenda</span>
            {data.semantic && <span>semantic</span>}
          </p>
        )}
      </div>

      <Toolbar
        query={query}
        onQuery={setQuery}
        view={state.view}
        onView={(v) => update({ view: v })}
        days={days}
        day={day}
        today={today}
        onDay={(d) => update({ day: d, from: null })}
        from={from}
        onFrom={(f) => update({ from: f })}
        filterCount={panelCount(filters)}
        filtersOpen={filtersOpen}
        onToggleFilters={() => setFiltersOpen(!filtersOpen)}
        sort={state.sort}
        onSort={(s) => update({ sort: s })}
      />

      {filtersOpen && (
        <FilterPanel
          facets={data?.facets}
          filters={filters}
          onChange={setFilters}
          onClear={() => setFilters({ ...NO_FILTERS, topics: filters.topics })}
          onClose={() => setFiltersOpen(false)}
        />
      )}

      {search.status === 'unavailable' && <p className="sch-note">Search is not available yet</p>}
      {agendaFailed && (
        <p className="sch-note sch-agenda-error" role="alert">
          Could not change your agenda. Try again.
        </p>
      )}

      {showResults ? (
        search.status === 'ready' ? (
          <SearchResults
            data={search.data}
            day={day ?? ''}
            onPickDay={(d) => update({ day: d, from: null })}
            agendaIds={agendaIds}
            onToggleAgenda={meta ? toggleAgenda : undefined}
          />
        ) : (
          <p className="sch-note sch-searching" role="status">
            <LoaderCircle size={14} className="sch-spin" aria-hidden="true" />
            Searching&hellip;
          </p>
        )
      ) : (
        <>
          {data && (
            <InterestChips
              interests={data.interests ?? []}
              selected={filters.topics}
              onToggle={toggleTopic}
              onEdit={openProfile}
            />
          )}
          {filtered && narrowed && (
            <p className="sch-note sch-showing" role="status">
              <span>
                Showing {shownCount} {state.view === 'all' ? '' : 'for you '}
                {shownCount === 1 ? 'session' : 'sessions'}
                {from === 'now' && day === today && ' from now'}
              </span>
              {anyFilter(filters) && (
                <button type="button" className="sch-link" onClick={() => setFilters(NO_FILTERS)}>
                  Clear filters
                </button>
              )}
            </p>
          )}

          {view.status === 'loading' && <p className="sch-note">Loading the schedule&hellip;</p>}
          {view.status === 'error' && <p className="sch-note">Could not load the schedule. Is the API running?</p>}
          {view.status === 'empty' && (
            <p className="sch-note">No schedule is loaded yet. Run the data loader (see the README) and reload.</p>
          )}
          {filtered && (
            <DayView
              data={filtered}
              forYouOnly={state.view === 'foryou'}
              sort={state.sort}
              onToggleAgenda={toggleAgenda}
            />
          )}
          {data && (
            <p className="sample-note">
              Meetings, agenda items and who is going are generated sample data.
            </p>
          )}
        </>
      )}
    </section>
  )
}
