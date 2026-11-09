import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { LoaderCircle, Search, SearchX, X } from 'lucide-react'
import { DEMO_USER, getJSON } from '../api.ts'
import ConnectionsTab from '../components/connect/ConnectionsTab.tsx'
import type { ConnectResponse, Meeting } from '../components/connect/types.ts'
import GroupsTab from '../components/groups/GroupsTab.tsx'
import type { Basis, ProposeSeed } from '../components/groups/types.ts'
import MatchFilters from '../components/people/MatchFilters.tsx'
import PersonCard from '../components/people/PersonCard.tsx'
import { WHY_FILTER } from '../components/people/fields.ts'
import type { FilterKey, Filters, Kind, MatchResponse, Why } from '../components/people/types.ts'
import '../styles/people.css'
import '../styles/connect.css'
import '../styles/groups.css'

const KINDS: { value: Kind; label: string }[] = [
  { value: 'attendee', label: 'Attendees' },
  { value: 'speaker', label: 'Speakers' },
]

type Tab = 'match' | 'connections' | 'groups'
const TABS: { value: Tab; label: string; lead: string }[] = [
  {
    value: 'match',
    label: 'Match',
    lead: 'People worth meeting, ranked by what you share. Click a reason to see everyone who shares it.',
  },
  { value: 'connections', label: 'Connections', lead: 'Meeting requests to and from you, and the meetings you have.' },
  {
    value: 'groups',
    label: 'Groups',
    lead: 'Meetups for people who share your school, country, company, community or interests.',
  },
]

function initialTab(): Tab {
  const t = new URLSearchParams(window.location.search).get('tab')
  return TABS.some((x) => x.value === t) ? (t as Tab) : 'match'
}

export default function People() {
  const [tab, setTabState] = useState<Tab>(initialTab)
  const [seed, setSeed] = useState<ProposeSeed | null>(null)
  const tabRefs = useRef<Record<Tab, HTMLButtonElement | null>>({ match: null, connections: null, groups: null })
  const [connectVersion, setConnectVersion] = useState(0)
  const [kind, setKind] = useState<Kind>('attendee')
  // My brief links here with ?q=<name> to open one person.
  const [text, setText] = useState(() => new URLSearchParams(window.location.search).get('q') ?? '')
  const [q, setQ] = useState(text)
  const [filters, setFilters] = useState<Filters>({})
  // The last response stays on screen while the next one loads, so cards and chips do not flicker.
  // `key` says which request it answered; loading is simply "the current request has not answered yet".
  const [res, setRes] = useState<{ key: string; data: MatchResponse | null; failed: boolean }>({
    key: '',
    data: null,
    failed: false,
  })
  // Meet: who the user already asked (pending) and who they are meeting (confirmed), by person id.
  const [requested, setRequested] = useState<Map<string, Meeting>>(new Map())
  const [meetings, setMeetings] = useState<Map<string, Meeting>>(new Map())
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

  // Reloaded when the Connections tab changes something, so Match cards show the same state.
  useEffect(() => {
    const ctrl = new AbortController()
    getJSON<ConnectResponse>('connect', { user_id: DEMO_USER }, { signal: ctrl.signal })
      .then((c) => {
        setRequested(new Map(c.outgoing.map((m) => [m.with_id, m])))
        setMeetings(new Map(c.meetings.map((m) => [m.with_id, m])))
      })
      .catch((err: unknown) => !ctrl.signal.aborted && console.warn('connections failed', err))
    return () => ctrl.abort()
  }, [connectVersion])

  // The tab lives in the address (?tab=groups) so it survives a reload and can be linked to.
  const setTab = (next: Tab, proposal: ProposeSeed | null = null) => {
    setTabState(next)
    setSeed(proposal)
    const url = new URL(window.location.href)
    if (next === 'match') url.searchParams.delete('tab')
    else url.searchParams.set('tab', next)
    window.history.replaceState(window.history.state, '', url)
  }

  const onTabKey = (e: KeyboardEvent) => {
    const i = TABS.findIndex((t) => t.value === tab)
    const step = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
    const to = e.key === 'Home' ? 0 : e.key === 'End' ? TABS.length - 1 : step ? (i + step + TABS.length) % TABS.length : -1
    if (to < 0) return
    e.preventDefault()
    setTab(TABS[to].value)
    tabRefs.current[TABS[to].value]?.focus()
  }

  const propose = (basis: Basis, value: string) => setTab('groups', { basis, value })

  const addRequested = (m: Meeting) => setRequested((prev) => new Map(prev).set(m.with_id, m))
  const removeRequested = (personId: string) =>
    setRequested((prev) => {
      const next = new Map(prev)
      next.delete(personId)
      return next
    })

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
      <p className="page-lead">{TABS.find((t) => t.value === tab)?.lead}</p>

      <div className="people-tabs" role="tablist" aria-label="People views" onKeyDown={onTabKey}>
        {TABS.map((t) => (
          <button
            key={t.value}
            ref={(el) => {
              tabRefs.current[t.value] = el
            }}
            id={`people-tab-${t.value}`}
            type="button"
            role="tab"
            aria-selected={tab === t.value}
            aria-controls={`people-panel-${t.value}`}
            tabIndex={tab === t.value ? 0 : -1}
            className="people-tab"
            onClick={() => setTab(t.value)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'connections' && (
        <div id="people-panel-connections" role="tabpanel" aria-labelledby="people-tab-connections">
          <ConnectionsTab userId={DEMO_USER} onChanged={() => setConnectVersion((v) => v + 1)} />
        </div>
      )}

      {tab === 'groups' && (
        <div id="people-panel-groups" role="tabpanel" aria-labelledby="people-tab-groups">
          <GroupsTab userId={DEMO_USER} seed={seed} />
        </div>
      )}

      {tab === 'match' && (
      <div id="people-panel-match" role="tabpanel" aria-labelledby="people-tab-match">
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
                <PersonCard
                  person={p}
                  onWhy={applyWhy}
                  userId={DEMO_USER}
                  request={requested.get(p.id)}
                  meeting={meetings.get(p.id)}
                  onRequested={addRequested}
                  onWithdrawn={removeRequested}
                  onPropose={propose}
                />
              </li>
            ))}
          </ol>
        )}
      </div>
      </div>
      )}
    </section>
  )
}
