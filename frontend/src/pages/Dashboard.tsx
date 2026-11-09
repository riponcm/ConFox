import { useCallback, useEffect, useState } from 'react'
import { BarChart3, Building2, Clock, Database, Globe, Layers, RefreshCw } from 'lucide-react'
import { getJSON } from '../api.ts'
import HealthLine from '../components/HealthLine.tsx'
import HeroRow from '../components/dashboard/HeroRow.tsx'
import NextUp from '../components/dashboard/NextUp.tsx'
import RankList from '../components/dashboard/RankList.tsx'
import StatRow from '../components/dashboard/StatRow.tsx'
import TimelineChart from '../components/dashboard/TimelineChart.tsx'
import { type DashboardData, dayLabel, hhmm } from '../components/dashboard/types.ts'
import '../styles/dashboard.css'

export default function Dashboard() {
  // null means "the API decides": the day of the demo clock.
  const [day, setDay] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const retry = useCallback(() => setAttempt((a) => a + 1), [])
  // The last data that arrived stays on screen (dimmed) while a new day loads.
  const [data, setData] = useState<DashboardData | null>(null)
  const [settled, setSettled] = useState<{ key: string; error: string | null } | null>(null)
  const key = `${day ?? 'today'}#${attempt}`
  const loading = settled?.key !== key
  const error = loading ? null : settled.error

  useEffect(() => {
    const ctrl = new AbortController()
    getJSON<DashboardData>('dashboard', { day }, { signal: ctrl.signal })
      .then((d) => {
        setData(d)
        setSettled({ key, error: null })
      })
      .catch((e: unknown) => {
        if (ctrl.signal.aborted) return
        setSettled({ key, error: e instanceof Error ? e.message : 'Request failed' })
      })
    return () => ctrl.abort()
  }, [day, key])

  const today = data?.is_today ? data.day : null
  const selected = data?.day ?? day

  return (
    <section className="page dashboard" aria-labelledby="page-title" aria-busy={loading}>
      <header className="dash-head">
        <div>
          <h1 id="page-title">Dashboard</h1>
          <p className="page-lead">
            The conference pulse
            {data ? ` for ${dayLabel(data.day, 'long')}` : ''}
            {data?.is_today ? `, as of ${hhmm(data.now)}` : ''}.
          </p>
        </div>
        {data && data.days.length > 1 && (
          <div className="dash-days" role="group" aria-label="Day">
            {data.days.map((d) => (
              <button
                key={d.day}
                type="button"
                className="dash-day"
                aria-pressed={d.day === selected}
                onClick={() => setDay(d.day)}
                disabled={loading && d.day === selected}
              >
                {dayLabel(d.day)}
                {d.day === today && <span className="dash-sr-only"> (today)</span>}
              </button>
            ))}
          </div>
        )}
      </header>

      {error && (
        <div className="dash-error" role="alert">
          <p>Could not load the dashboard ({error}).</p>
          <button type="button" className="dash-retry" onClick={retry}>
            <RefreshCw size={15} aria-hidden="true" />
            Try again
          </button>
        </div>
      )}

      {!data && loading && !error && (
        <p className="dash-loading" role="status">
          Loading the conference pulse...
        </p>
      )}

      {data && (
        <div className={loading ? 'dash-body is-refreshing' : 'dash-body'}>
          {data.is_today && <HeroRow />}
          <StatRow data={data} dayName={dayLabel(data.day)} />

          <article className="dash-card dash-card-wide" aria-labelledby="dash-timeline-title">
            <h2 id="dash-timeline-title" className="dash-card-title">
              <BarChart3 size={16} aria-hidden="true" />
              Sessions through the day
            </h2>
            <p className="dash-card-sub">Sessions starting in each half hour, by kind.</p>
            <TimelineChart data={data} />
          </article>

          <div className="dash-grid">
            <article className="dash-card" aria-labelledby="dash-next-title">
              <h2 id="dash-next-title" className="dash-card-title">
                <Clock size={16} aria-hidden="true" />
                Starting soon
              </h2>
              <p className="dash-card-sub">The next 90 minutes, registration left out.</p>
              <NextUp data={data} />
            </article>

            <article className="dash-card" aria-labelledby="dash-tracks-title">
              <h2 id="dash-tracks-title" className="dash-card-title">
                <Layers size={16} aria-hidden="true" />
                {data.is_today ? 'Top tracks today' : `Top tracks on ${dayLabel(data.day)}`}
              </h2>
              <p className="dash-card-sub">Sessions per track.</p>
              <RankList
                label="Top tracks"
                unit="sessions"
                items={data.tracks.map((t) => ({ name: t.name, value: t.sessions }))}
              />
            </article>

            <article className="dash-card" aria-labelledby="dash-countries-title">
              <h2 id="dash-countries-title" className="dash-card-title">
                <Globe size={16} aria-hidden="true" />
                Where attendees come from
              </h2>
              <p className="dash-card-sub">
                <span className="chip chip-warn">Sample data</span> Generated attendee profiles.
              </p>
              <RankList
                label="Attendee countries"
                unit="attendees"
                items={data.people.countries.map((c) => ({ name: c.name, value: c.attendees }))}
              />
            </article>

            <article className="dash-card" aria-labelledby="dash-companies-title">
              <h2 id="dash-companies-title" className="dash-card-title">
                <Building2 size={16} aria-hidden="true" />
                Companies with the most speakers
              </h2>
              <p className="dash-card-sub">Speakers per company, from the public schedule.</p>
              <RankList
                label="Speaker companies"
                unit="speakers"
                items={data.people.companies.map((c) => ({ name: c.name, value: c.speakers }))}
              />
            </article>
          </div>
        </div>
      )}

      <footer className="dash-foot">
        <p className="dash-source">
          <Database size={14} aria-hidden="true" />
          Every number here comes from Elasticsearch aggregations over the public schedule. Attendee profiles are
          generated sample data.
        </p>
        <HealthLine />
      </footer>
    </section>
  )
}
