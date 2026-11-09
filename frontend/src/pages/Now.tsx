import { useEffect, useState } from 'react'
import { useAgendaVersion } from '../components/session/context.ts'
import { Link } from 'react-router'
import { CalendarDays, ChevronDown, Coffee, FileText, Radio, Users } from 'lucide-react'
import { DEMO_USER, getJSON } from '../api.ts'
import { hhmm, roomLabel, timeRange } from '../components/schedule/time.ts'
import type { Session } from '../types.ts'
import SessionLink from '../components/session/SessionLink.tsx'
import '../styles/now.css'
import { useProfileVersion } from '../profile.ts'

type Food = { session: Session; status: 'now' | 'next'; minutes: number }
type AgendaItem = { title: string; kind: string; with_name?: string; starts_at: string; ends_at: string; room?: string }
type NowSession = Session & { short_title: string; going: number; on_agenda?: boolean }
type Featured = NowSession & { friends: string[]; why: string[] }
type Item = {
  id: string
  type: 'session' | 'meeting' | 'food'
  source: 'agenda' | 'food' | 'for_you'
  title: string
  starts_at: string
  ends_at: string
  room: string
  with_name: string | null
  all_day: boolean
  minutes_from_now: number
  why: string[]
}
type Slot = { starts_at: string; minutes_from_now: number; food: boolean; featured: Featured | null; others: NowSession[] }
type NowResponse = {
  now: string
  simulated: boolean
  on_now: NowSession[]
  on_now_total: number
  soon_total: number
  food: Food | null
  my_next: AgendaItem | null
  next: Item | null
  then: Item | null
  horizon_minutes: number
  slots: Slot[]
}

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "2026-11-09T08:40:00" -> "Mon, Nov 9". Date.UTC keeps the calendar date whatever the browser's zone. */
function longDate(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  return `${WEEKDAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()]}, ${MONTHS[m - 1]} ${d}`
}

function duration(n: number): string {
  if (n < 60) return `${n} min`
  const h = Math.floor(n / 60)
  const m = n % 60
  return m ? `${h} h ${m} min` : `${h} h`
}

function relative(n: number): string {
  return n <= 0 ? 'now' : `in ${duration(n)}`
}

function itemTitle(item: Item): string {
  return item.type === 'meeting' && item.with_name ? `${item.title} with ${item.with_name}` : item.title
}

function joinDot(parts: (string | null | undefined)[]): string {
  return parts.filter(Boolean).join(' · ')
}

function titles(list: NowSession[], max = 3): string {
  const shown = list.slice(0, max).map((s) => s.short_title)
  return list.length > max ? `${shown.join(', ')}, …` : shown.join(', ')
}

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}

function Hero({ next, then }: { next: Item | null; then: Item | null }) {
  return (
    <section className="now-hero" aria-label="Where to be next">
      <div className="now-hero-col">
        <p className="now-hero-label">Where to be next</p>
        {next ? (
          <>
            <p className="now-hero-title">{itemTitle(next)}</p>
            <p className="now-hero-when">
              {relative(next.minutes_from_now)}{' '}
              <span className="now-hero-at">
                at <time dateTime={next.starts_at}>{hhmm(next.starts_at)}</time>
              </span>
            </p>
            <p className="now-hero-sub">
              {joinDot([roomLabel(next.room), next.source === 'agenda' ? 'on your agenda' : next.why[0]])}
            </p>
          </>
        ) : (
          <>
            <p className="now-hero-title">Nothing planned yet</p>
            <p className="now-hero-sub">
              <Link to="/schedule">Pick something from the schedule</Link>
            </p>
          </>
        )}
      </div>
      <div className="now-hero-col now-hero-then">
        <p className="now-hero-label">Then</p>
        {then ? (
          <>
            <p className="now-hero-then-title">
              {itemTitle(then)}{' '}
              <time dateTime={then.starts_at}>{timeRange(then.starts_at, then.ends_at)}</time>
            </p>
            <p className="now-hero-sub">{joinDot([roomLabel(then.room), relative(then.minutes_from_now)])}</p>
          </>
        ) : (
          <p className="now-hero-sub">Nothing else on your agenda today.</p>
        )}
      </div>
    </section>
  )
}

function CompactList({ sessions, id }: { sessions: NowSession[]; id: string }) {
  return (
    <ul className="now-compact" id={id}>
      {sessions.map((s) => (
        <li key={s.id}>
          <time dateTime={s.starts_at}>{timeRange(s.starts_at, s.ends_at)}</time>
          <SessionLink id={s.id} className="now-compact-title">{s.short_title}</SessionLink>
          <span className="now-compact-meta">
            {joinDot([roomLabel(s.room), s.going ? `${s.going} going` : null])}
          </span>
        </li>
      ))}
    </ul>
  )
}

/** A muted summary line ("+8 more sessions · A, B, … · show") that expands into compact rows. */
function MoreLine({ lead, sessions, id, preview }: { lead: string; sessions: NowSession[]; id: string; preview?: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="now-more">
      <p className="now-more-line">
        <span className="now-more-lead">{lead}</span>
        {!open && <span className="now-more-titles"> · {preview ?? titles(sessions)}</span>}{' '}
        <button type="button" className="now-more-toggle" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}>
          {open ? 'hide' : sessions.length > 1 ? `show all ${sessions.length}` : 'show'}
          <ChevronDown size={14} aria-hidden="true" className={open ? 'is-open' : undefined} />
        </button>
      </p>
      {open && <CompactList sessions={sessions} id={id} />}
    </div>
  )
}

function FeaturedCard({ s }: { s: Featured }) {
  const why = s.why[0]
  return (
    <article className="now-feat">
      <div className="now-feat-top">
        <h3 className="now-feat-title"><SessionLink id={s.id}>{s.short_title}</SessionLink></h3>
        {why && <span className={s.on_agenda ? 'chip now-chip-mine' : 'chip'}>{why}</span>}
      </div>
      <p className="now-feat-meta">
        <time dateTime={s.starts_at}>{timeRange(s.starts_at, s.ends_at)}</time>
        <span>{roomLabel(s.room)}</span>
      </p>
      <p className="now-feat-foot">
        {s.track && <span className="now-track">{s.track}</span>}
        {s.going > 0 && (
          <span className="now-going">
            <Users size={14} aria-hidden="true" />
            {joinDot([`${s.going} going`, s.friends.join(', ')])}
          </span>
        )}
      </p>
    </article>
  )
}

function SlotRow({ slot }: { slot: Slot }) {
  const when = <TimeCell iso={slot.starts_at} rel={relative(slot.minutes_from_now)} />
  if (slot.food) {
    return (
      <li className="now-tl-row is-food">
        {when}
        <div className="now-tl-body">
          {slot.others.map((s) => (
            <p key={s.id} className="now-food">
              <Coffee size={15} aria-hidden="true" />
              <span>{joinDot([s.short_title, roomLabel(s.room)])}</span>
              <time dateTime={s.ends_at}>until {hhmm(s.ends_at)}</time>
            </p>
          ))}
        </div>
      </li>
    )
  }
  const others = slot.others
  const id = `slot-${slot.starts_at.slice(11, 16).replace(':', '')}`
  return (
    <li className={slot.featured ? 'now-tl-row is-featured' : 'now-tl-row'}>
      {when}
      <div className="now-tl-body">
        {slot.featured && <FeaturedCard s={slot.featured} />}
        {!slot.featured && others.length === 1 ? (
          <CompactList sessions={others} id={id} />
        ) : others.length > 0 ? (
          <MoreLine
            lead={slot.featured ? `+${others.length} more` : plural(others.length, 'session')}
            sessions={others}
            id={id}
          />
        ) : null}
      </div>
    </li>
  )
}

function TimeCell({ iso, rel }: { iso: string; rel: string }) {
  return (
    <div className="now-tl-time">
      <time dateTime={iso}>{hhmm(iso)}</time>
      <span>{rel}</span>
    </div>
  )
}

export default function Now() {
  const [data, setData] = useState<NowResponse | null>(null)
  const [failed, setFailed] = useState(false)

  const agendaVersion = useAgendaVersion()
  const profileVersion = useProfileVersion()

  useEffect(() => {
    getJSON<NowResponse>('now', { user_id: DEMO_USER })
      .then(setData)
      .catch(() => setFailed(true))
  }, [agendaVersion, profileVersion]) // refetch after agenda or profile changes

  return (
    <section className="page now" aria-labelledby="page-title">
      <header className="now-head">
        <div className="now-head-text">
          <h1 id="page-title">Right now</h1>
          {data && (
            <p className="now-head-meta">
              {longDate(data.now)}, <time dateTime={data.now}>{hhmm(data.now)}</time> · Salt Palace
              {data.simulated && ' · simulated clock'}
            </p>
          )}
        </div>
        <Link className="btn-primary now-brief" to="/brief">
          <FileText size={16} aria-hidden="true" /> My brief
        </Link>
      </header>

      {failed && <p className="page-lead">Could not load what is on now. Is the API running?</p>}
      {!data && !failed && <p className="page-lead">Loading&hellip;</p>}
      {data && (
        <>
          <Hero next={data.next} then={data.then} />

          <div className="now-sec-head">
            <h2>Next two hours</h2>
            <Link to="/schedule" className="now-sec-link">
              <CalendarDays size={15} aria-hidden="true" /> Full schedule
            </Link>
          </div>

          <ol className="now-tl">
            <li className="now-tl-row is-now">
              <TimeCell iso={data.now} rel="now" />
              <div className="now-tl-body">
                {data.on_now_total ? (
                  <MoreLine
                    lead={`${data.on_now_total} on now`}
                    sessions={data.on_now}
                    id="on-now"
                    preview={[data.on_now[0]?.short_title, roomLabel(data.on_now[0]?.room)].filter(Boolean).join(', ')}
                  />
                ) : (
                  <p className="now-more-line">
                    <Radio size={14} aria-hidden="true" /> Nothing is running right now.
                  </p>
                )}
              </div>
            </li>
            {data.slots.map((slot) => (
              <SlotRow key={`${slot.starts_at}-${slot.food}`} slot={slot} />
            ))}
            {data.slots.length === 0 && (
              <li className="now-tl-row">
                <div className="now-tl-time" />
                <div className="now-tl-body">
                  <p className="now-more-line">Nothing else starts in the next two hours.</p>
                </div>
              </li>
            )}
          </ol>

          <p className="sample-note">
            Agenda, going counts and names include generated sample data.
          </p>
        </>
      )}
    </section>
  )
}
