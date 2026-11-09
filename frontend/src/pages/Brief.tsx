import { useCallback, useEffect, useState } from 'react'
import { CalendarDays, RefreshCw, Sparkles, Users } from 'lucide-react'
import { DEMO_USER, getJSON } from '../api.ts'
import { useProfileVersion } from '../profile.ts'
import SessionCard from '../components/SessionCard.tsx'
import DayTimeline from '../components/brief/DayTimeline.tsx'
import PeopleToday from '../components/brief/PeopleToday.tsx'
import { longDay } from '../components/brief/types.ts'
import type { BriefResponse } from '../components/brief/types.ts'
import '../styles/brief.css'

export default function Brief() {
  const [data, setData] = useState<BriefResponse | null>(null)
  const [failed, setFailed] = useState(false)
  // Suggested people and sessions follow the saved profile; a save bumps the version and the brief reloads.
  const version = useProfileVersion()

  const fetchBrief = useCallback(() => {
    getJSON<BriefResponse>('brief', { user_id: DEMO_USER })
      .then((d) => {
        setData(d)
        setFailed(false)
      })
      .catch(() => setFailed(true))
  }, [])

  useEffect(fetchBrief, [fetchBrief, version])

  const load = () => {
    setFailed(false)
    fetchBrief()
  }

  if (failed && !data) {
    return (
      <section className="page brief" aria-labelledby="page-title">
        <h1 id="page-title">My brief</h1>
        <div className="brief-error" role="alert">
          <p>Could not load your brief. Is the API running?</p>
          <button type="button" className="brief-btn" onClick={load}>
            <RefreshCw size={15} aria-hidden="true" /> Try again
          </button>
        </div>
      </section>
    )
  }

  if (!data) {
    return (
      <section className="page brief" aria-labelledby="page-title" aria-busy="true">
        <h1 id="page-title">My brief</h1>
        <p className="page-lead">Loading your day&hellip;</p>
        <div className="brief-skeleton" aria-hidden="true" />
        <div className="brief-skeleton brief-skeleton-tall" aria-hidden="true" />
      </section>
    )
  }

  const meetings = data.timeline.filter((i) => i.type === 'meeting')
  return (
    <section className="page brief" aria-labelledby="page-title">
      <header className="brief-head">
        <p className="brief-eyebrow">My brief</p>
        <h1 id="page-title">
          {longDay(data.day)} <span className="brief-for">for {data.user.first_name}</span>
        </h1>
      </header>
      <p className="brief-summary">{data.summary}</p>
      {failed && (
        <div className="brief-error" role="alert">
          <p>Could not refresh your brief, so it may be out of date.</p>
          <button type="button" className="brief-btn" onClick={load}>
            <RefreshCw size={15} aria-hidden="true" /> Try again
          </button>
        </div>
      )}

      <h2 className="brief-h">
        <Users size={16} aria-hidden="true" /> People today
      </h2>
      <PeopleToday
        meetings={meetings}
        incoming={data.requests.incoming}
        outgoing={data.requests.outgoing}
        people={data.people}
        onChanged={load}
      />

      <h2 className="brief-h">
        <CalendarDays size={16} aria-hidden="true" /> Your day
      </h2>
      <DayTimeline items={data.timeline} gaps={data.gaps} now={data.now} />

      <h2 className="brief-h">
        <Sparkles size={16} aria-hidden="true" /> Suggested for you
      </h2>
      {data.suggested.length ? (
        <ul className="brief-suggested" role="list">
          {data.suggested.map((s) => (
            <li key={s.id}>
              <SessionCard session={s} />
              {s.why.length > 0 && <p className="brief-why">{s.why.join(' · ')}</p>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="brief-empty">No more sessions today match your interests.</p>
      )}

      <p className="sample-note">Agenda items and people are generated sample data.</p>
    </section>
  )
}
