import { type ReactNode, useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'
import type { LucideIcon } from 'lucide-react'
import {
  Activity,
  BarChart3,
  Building2,
  CalendarRange,
  Database,
  Flame,
  Globe,
  GraduationCap,
  Layers,
  RefreshCw,
  Search,
  Sparkles,
  Sun,
} from 'lucide-react'
import { getJSON } from '../api.ts'
import HealthLine from '../components/HealthLine.tsx'
import ActivitySpark from '../components/dashboard/ActivitySpark.tsx'
import DashTiles from '../components/dashboard/DashTiles.tsx'
import RankList, { type RankItem } from '../components/dashboard/RankList.tsx'
import TimelineChart from '../components/dashboard/TimelineChart.tsx'
import { type DashboardData, type Named, dayLabel, fmt, hhmm } from '../components/dashboard/types.ts'
import '../styles/dashboard.css'

const named = (items: Named[]): RankItem[] =>
  items.map((i) => ({ name: i.name, value: i.count, tag: i.pinned ? 'Host city' : undefined }))

function Card({
  id,
  icon: Icon,
  title,
  sub,
  sample,
  children,
}: {
  id: string
  icon: LucideIcon
  title: string
  sub: string
  sample?: boolean
  children: ReactNode
}) {
  return (
    <article className="dash-card" aria-labelledby={`dash-${id}-title`}>
      <h2 id={`dash-${id}-title`} className="dash-card-title">
        <Icon size={16} aria-hidden="true" />
        {title}
      </h2>
      <p className="dash-card-sub">
        {sub}
        {sample && <span className="chip chip-warn">Sample</span>}
      </p>
      {children}
    </article>
  )
}

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
  const on = data?.is_today ? 'today' : data ? `on ${dayLabel(data.day)}` : ''

  return (
    <section className="page dashboard" aria-labelledby="page-title" aria-busy={loading}>
      <header className="dash-head">
        <div className="dash-head-text">
          <h1 id="page-title">Dashboard</h1>
          <p className="page-lead">
            {data && (
              <>
                {dayLabel(data.day, 'long')}
                {data.is_today && (
                  <>
                    , <time dateTime={data.now}>{hhmm(data.now)}</time>
                  </>
                )}{' '}
                &middot;{' '}
              </>
            )}
            Salt Palace &middot; live from Elasticsearch
          </p>
        </div>
        <div className="dash-head-actions">
          <Link to="/brief" className="btn-primary dash-brief">
            <Sun size={15} aria-hidden="true" />
            My brief
          </Link>
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
        </div>
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
          <DashTiles data={data} />

          <article className="dash-card" aria-labelledby="dash-timeline-title">
            <h2 id="dash-timeline-title" className="dash-card-title">
              <BarChart3 size={16} aria-hidden="true" />
              {data.is_today ? 'Today at a glance' : `${dayLabel(data.day)} at a glance`}
            </h2>
            <p className="dash-card-sub">Sessions starting each half hour.</p>
            <TimelineChart data={data} />
          </article>

          <div className="dash-grid">
            <Card id="filling" icon={Flame} title="Filling up next" sub="Most-added upcoming sessions." sample>
              <RankList
                label="Most-added upcoming sessions"
                unit="going"
                suffix="going"
                empty="Nothing left to start on this day."
                items={data.filling.map((s) => ({ name: s.title, value: s.going, time: s.starts_at, sessionId: s.id }))}
              />
            </Card>

            <Card id="tracks" icon={Layers} title={`Tracks ${on}`} sub="Sessions by track.">
              <RankList
                label="Sessions by track"
                unit="sessions"
                items={data.tracks.map((t) => ({ name: t.name, value: t.sessions }))}
              />
            </Card>

            <Card id="week" icon={CalendarRange} title="Week" sub="Sessions per day.">
              <RankList
                label="Sessions per day"
                unit="sessions"
                items={data.days.map((d) => ({
                  name: `${dayLabel(d.day)}${d.day === today ? ' (today)' : ''}`,
                  value: d.sessions,
                }))}
              />
            </Card>

            <Card
              id="activity"
              icon={Activity}
              title="Confox activity"
              sub={`${fmt(data.activity.total)} interactions ${on}: searches, agenda adds, matches, questions.`}
              sample={data.activity.sample > 0}
            >
              <ActivitySpark data={data} />
            </Card>

            <Card id="countries" icon={Globe} title="Where people are from" sub="Attendees by country." sample>
              <RankList label="Attendees by country" unit="attendees" items={named(data.people.countries)} />
            </Card>

            <Card id="searches" icon={Search} title="What people want" sub="Top searches this week." sample>
              <RankList
                label="Top searches"
                unit="searches"
                empty="No searches yet."
                items={named(data.activity.searches)}
              />
            </Card>

            <Card id="schools" icon={GraduationCap} title="Universities here" sub="Alumni groups among attendees." sample>
              <RankList label="Attendees by university" unit="attendees" items={named(data.people.schools)} />
            </Card>

            <Card id="companies" icon={Building2} title="Companies here" sub="Attendees by employer." sample>
              <RankList label="Attendees by employer" unit="attendees" items={named(data.people.companies)} />
            </Card>

            <Card id="interests" icon={Sparkles} title="Interests" sub="What attendees follow." sample>
              <RankList label="Attendee interests" unit="attendees" items={named(data.people.interests)} />
            </Card>
          </div>
        </div>
      )}

      <footer className="dash-foot">
        <p className="dash-source">
          <Database size={14} aria-hidden="true" />
          Every number here comes from Elasticsearch aggregations over the public schedule. Attendee profiles, agendas
          and most activity are generated sample data, marked Sample.
        </p>
        <HealthLine />
      </footer>
    </section>
  )
}
