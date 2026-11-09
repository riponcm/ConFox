import { useEffect, useState } from 'react'
import { CalendarCheck, Coffee, Radio, Timer } from 'lucide-react'
import { DEMO_USER, getJSON } from '../api.ts'
import SessionCard from '../components/SessionCard.tsx'
import SessionLink from '../components/session/SessionLink.tsx'
import { dayLabel, hhmm, roomLabel } from '../components/schedule/time.ts'
import type { Session } from '../types.ts'
import '../styles/now.css'

type Food = { session: Session; status: 'now' | 'next'; minutes: number }
type AgendaItem = {
  title: string
  kind: string
  with_name?: string
  session_id?: string
  starts_at: string
  ends_at: string
  room?: string
}
type NowResponse = {
  now: string
  on_now: Session[]
  on_now_total: number
  soon: Session[]
  soon_total: number
  food: Food | null
  my_next: AgendaItem | null
}

function inMinutes(n: number): string {
  if (n < 60) return `${n} min`
  const h = Math.floor(n / 60)
  const m = n % 60
  return m ? `${h} h ${m} min` : `${h} h`
}

export default function Now() {
  const [data, setData] = useState<NowResponse | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    getJSON<NowResponse>('now', { user_id: DEMO_USER })
      .then(setData)
      .catch(() => setFailed(true))
  }, [])

  return (
    <section className="page now" aria-labelledby="page-title">
      <h1 id="page-title">Now</h1>
      {failed && <p className="page-lead">Could not load what is on now. Is the API running?</p>}
      {!data && !failed && <p className="page-lead">Loading&hellip;</p>}
      {data && (
        <>
          <p className="page-lead">
            It is <time dateTime={data.now}>{hhmm(data.now)}</time> on {dayLabel(data.now.slice(0, 10))}.
          </p>

          <div className="now-tiles">
            <article className="now-tile now-tile-food">
              <h2>
                <Coffee size={16} aria-hidden="true" /> Next coffee or food
              </h2>
              {data.food ? (
                <>
                  <p className="now-big">
                    <SessionLink id={data.food.session.id}>{data.food.session.title}</SessionLink>
                    {data.food.status === 'now'
                      ? ` now, ${inMinutes(data.food.minutes)} left`
                      : ` in ${inMinutes(data.food.minutes)}`}
                  </p>
                  <p className="now-sub">
                    {hhmm(data.food.session.starts_at)}&ndash;{hhmm(data.food.session.ends_at)} &middot;{' '}
                    {roomLabel(data.food.session.room)}
                  </p>
                </>
              ) : (
                <p className="now-big">No more food breaks today</p>
              )}
            </article>

            <article className="now-tile">
              <h2>
                <CalendarCheck size={16} aria-hidden="true" /> Your next
              </h2>
              {data.my_next ? (
                <>
                  <p className="now-big">
                    {data.my_next.kind === 'meeting' && data.my_next.with_name ? (
                      `${data.my_next.title} with ${data.my_next.with_name}`
                    ) : data.my_next.session_id ? (
                      <SessionLink id={data.my_next.session_id}>{data.my_next.title}</SessionLink>
                    ) : (
                      data.my_next.title
                    )}
                  </p>
                  <p className="now-sub">
                    {hhmm(data.my_next.starts_at)}&ndash;{hhmm(data.my_next.ends_at)}
                    {data.my_next.room ? <> &middot; {roomLabel(data.my_next.room)}</> : null}
                  </p>
                </>
              ) : (
                <p className="now-big">Nothing else on your agenda today</p>
              )}
            </article>
          </div>

          <h2 className="now-h">
            <Radio size={16} aria-hidden="true" /> On now <span className="now-count">{data.on_now_total}</span>
          </h2>
          {data.on_now.length ? (
            <ul className="now-list">
              {data.on_now.map((s) => (
                <li key={s.id}>
                  <SessionCard session={s} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="now-empty">Nothing is running right now.</p>
          )}

          <h2 className="now-h">
            <Timer size={16} aria-hidden="true" /> Starting in the next 90 minutes{' '}
            <span className="now-count">{data.soon_total}</span>
          </h2>
          {data.soon.length ? (
            <ul className="now-list">
              {data.soon.map((s) => (
                <li key={s.id}>
                  <SessionCard session={s} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="now-empty">Nothing else starts in the next 90 minutes.</p>
          )}
          <p className="sample-note">Agenda items are generated sample data.</p>
        </>
      )}
    </section>
  )
}
