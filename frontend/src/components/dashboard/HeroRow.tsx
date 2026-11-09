import { useEffect, useState } from 'react'
import { CalendarCheck, Coffee, Radio } from 'lucide-react'
import { DEMO_USER, getJSON } from '../../api.ts'
import { useProfileVersion } from '../../profile.ts'
import { hhmm, roomLabel } from '../schedule/time.ts'
import type { Session } from '../../types.ts'

type NowSummary = {
  on_now_total: number
  soon_total: number
  food: { session: Session; status: 'now' | 'next'; minutes: number } | null
  my_next: { title: string; kind: string; with_name?: string; starts_at: string; ends_at: string } | null
}

/** The personal top row of the Dashboard: next coffee (from next_food()), what is on, and the user's next item. */
export default function HeroRow() {
  const [now, setNow] = useState<NowSummary | null>(null)
  const version = useProfileVersion() // refetch after a profile save

  useEffect(() => {
    getJSON<NowSummary>('now', { user_id: DEMO_USER })
      .then(setNow)
      .catch(() => setNow(null))
  }, [version])

  if (!now) return null
  const food = now.food
  const mine = now.my_next
  return (
    <div className="dash-hero-row">
      <article className="dash-hero">
        <p className="dash-hero-label">
          <Coffee size={14} aria-hidden="true" /> {food?.status === 'now' ? 'Coffee now' : 'Next coffee'}
        </p>
        {food ? (
          <>
            <p className="dash-hero-big">
              <span className="dash-hero-num">{food.minutes}</span> min
              <span className="dash-hero-what"> &middot; {food.status === 'now' ? 'left of ' : ''}{food.session.title}</span>
            </p>
            <p className="dash-hero-sub">
              <time dateTime={food.session.starts_at}>{hhmm(food.session.starts_at)}</time>&ndash;
              <time dateTime={food.session.ends_at}>{hhmm(food.session.ends_at)}</time> &middot;{' '}
              {roomLabel(food.session.room)}
            </p>
          </>
        ) : (
          <p className="dash-hero-big">No more breaks today</p>
        )}
      </article>

      <article className="dash-tile">
        <p className="dash-tile-label">
          <Radio size={14} aria-hidden="true" /> Happening
        </p>
        <p className="dash-tile-big">
          <span className="dash-hero-num">{now.on_now_total}</span> on now
        </p>
        <p className="dash-tile-sub">{now.soon_total} starting in the next 90 min</p>
      </article>

      <article className="dash-tile">
        <p className="dash-tile-label">
          <CalendarCheck size={14} aria-hidden="true" /> Your next
        </p>
        {mine ? (
          <>
            <p className="dash-tile-big dash-tile-title">
              {mine.kind === 'meeting' && mine.with_name ? `${mine.title} with ${mine.with_name}` : mine.title}
            </p>
            <p className="dash-tile-sub">
              <time dateTime={mine.starts_at}>{hhmm(mine.starts_at)}</time>&ndash;
              <time dateTime={mine.ends_at}>{hhmm(mine.ends_at)}</time>
            </p>
            <p className="sample-note">Agenda items are generated sample data.</p>
          </>
        ) : (
          <p className="dash-tile-big">Nothing else today</p>
        )}
      </article>
    </div>
  )
}
