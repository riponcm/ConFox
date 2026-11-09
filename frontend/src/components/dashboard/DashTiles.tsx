import { useEffect, useState } from 'react'
import { useAgendaVersion } from '../session/context.ts'
import { CalendarCheck, CalendarDays, Coffee, Radio, Users } from 'lucide-react'
import { DEMO_USER, getJSON } from '../../api.ts'
import { roomLabel } from '../schedule/time.ts'
import type { Session } from '../../types.ts'
import { type DashboardData, dayLabel, fmt, hhmm, hours, plural } from './types.ts'

type NowSummary = {
  on_now_total: number
  soon_total: number
  food: { session: Session; status: 'now' | 'next'; minutes: number } | null
}

const RING_R = 17
const RING_C = 2 * Math.PI * RING_R

/** A small meter: the share of the goal the agenda covers. The track is a light step of the same accent. */
function Ring({ share, label }: { share: number; label: string }) {
  const filled = Math.min(1, Math.max(0, share))
  return (
    <svg className="dash-ring" width="44" height="44" viewBox="0 0 44 44" role="img" aria-label={label}>
      <circle cx="22" cy="22" r={RING_R} fill="none" stroke="var(--accent-soft)" strokeWidth="5" />
      {filled > 0 && (
        <circle
          cx="22"
          cy="22"
          r={RING_R}
          fill="none"
          stroke="var(--accent)"
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={`${RING_C * filled} ${RING_C}`}
          transform="rotate(-90 22 22)"
        />
      )}
    </svg>
  )
}

/** The top row: next coffee, what is happening, who is here and the user's day. Personal tiles show on today only. */
export default function DashTiles({ data }: { data: DashboardData }) {
  const [now, setNow] = useState<NowSummary | null>(null)
  const [failed, setFailed] = useState(false)

  const agendaVersion = useAgendaVersion()

  useEffect(() => {
    getJSON<NowSummary>('now', { user_id: DEMO_USER })
      .then(setNow)
      .catch(() => setFailed(true))
  }, [agendaVersion]) // refetch when the session drawer changes the agenda

  const people = data.people
  const peopleTile = (
    <article className="dash-tile">
      <p className="dash-tile-label">
        <Users size={14} aria-hidden="true" /> People here
      </p>
      <p className="dash-tile-big">
        <span className="dash-hero-num">{fmt(people.total)}</span> people
      </p>
      <p className="dash-tile-sub">
        {fmt(people.speakers)} speakers &middot; {fmt(people.attendees)}{' '}
        <span className="dash-sample-text">sample</span> attendees
      </p>
    </article>
  )

  if (!data.is_today) {
    return (
      <div className="dash-tiles is-day">
        <article className="dash-tile">
          <p className="dash-tile-label">
            <CalendarDays size={14} aria-hidden="true" /> {dayLabel(data.day)}
          </p>
          <p className="dash-tile-big">
            <span className="dash-hero-num">{fmt(data.sessions.day)}</span> sessions
          </p>
          <p className="dash-tile-sub">{fmt(data.sessions.total)} across the week</p>
        </article>
        {peopleTile}
      </div>
    )
  }

  const food = now?.food
  const mine = data.my_day
  const share = mine.hours / mine.goal_hours
  const parts = [plural(mine.sessions, 'session')]
  if (mine.meetings) parts.push(plural(mine.meetings, 'meeting'))
  parts.push(plural(mine.requests, 'meet request'))
  const waiting = failed ? 'Not available' : 'Loading...'

  return (
    <div className="dash-tiles">
      <article className="dash-hero">
        <p className="dash-hero-label">
          <Coffee size={14} aria-hidden="true" /> {food?.status === 'now' ? 'Coffee now' : 'Next coffee'}
        </p>
        {food ? (
          <>
            <p className="dash-hero-big">
              <span className="dash-hero-num">{food.minutes}</span> min
              <span className="dash-hero-what">
                {' '}
                &middot; {food.status === 'now' ? 'left of ' : ''}
                {food.session.title}
              </span>
            </p>
            <p className="dash-hero-sub">
              <time dateTime={food.session.starts_at}>{hhmm(food.session.starts_at)}</time>&ndash;
              <time dateTime={food.session.ends_at}>{hhmm(food.session.ends_at)}</time> &middot;{' '}
              {roomLabel(food.session.room)}
            </p>
          </>
        ) : (
          <p className="dash-hero-big">{now ? 'No more breaks today' : waiting}</p>
        )}
      </article>

      <article className="dash-tile">
        <p className="dash-tile-label">
          <Radio size={14} aria-hidden="true" /> Happening
        </p>
        {now ? (
          <p className="dash-tile-big">
            <span className="dash-hero-num">{fmt(now.on_now_total)}</span> on now
            <span className="dash-tile-aside"> &middot; {fmt(now.soon_total)} next 90 min</span>
          </p>
        ) : (
          <p className="dash-tile-big">{waiting}</p>
        )}
        <p className="dash-tile-sub">{plural(data.sessions.day, 'session')} today</p>
      </article>

      {peopleTile}

      <article className="dash-tile">
        <p className="dash-tile-label">
          <CalendarCheck size={14} aria-hidden="true" /> My day
        </p>
        <div className="dash-myday">
          <Ring
            share={share}
            label={`Confirmed agenda covers ${Math.round(Math.min(1, share) * 100)}% of an ${mine.goal_hours}-hour day`}
          />
          <div className="dash-myday-text">
            <p className="dash-tile-big">
              <span className="dash-hero-num">{hours(mine.hours)}</span> of {mine.goal_hours} hrs
            </p>
            <p className="dash-tile-sub">{parts.join(' · ')}</p>
          </div>
        </div>
        <p className="sample-note">Sample agenda.</p>
      </article>
    </div>
  )
}
