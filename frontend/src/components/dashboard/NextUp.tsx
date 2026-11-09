import { MapPin } from 'lucide-react'
import { type DashboardData, groupOf, hhmm, hhmmFromMinutes, minutesOf } from './types.ts'

const WINDOW_MINUTES = 90

export default function NextUp({ data }: { data: DashboardData }) {
  if (!data.is_today) {
    return <p className="dash-empty">Starting soon follows the current time, so it shows on today's dashboard.</p>
  }
  const until = hhmmFromMinutes(Math.min(24 * 60 - 1, minutesOf(data.now) + WINDOW_MINUTES))
  if (data.next_up.length === 0) {
    return <p className="dash-empty">Nothing else starts before {until}.</p>
  }
  const more = data.next_up_total - data.next_up.length

  return (
    <>
      <ol className="dash-next">
        {data.next_up.map((s) => {
          const group = groupOf(s.kind)
          return (
            <li key={s.id} className="dash-next-item">
              <time className="dash-next-time" dateTime={s.starts_at}>
                {hhmm(s.starts_at)}
              </time>
              <div className="dash-next-body">
                <p className="dash-next-title">{s.title}</p>
                <p className="dash-next-meta">
                  <span className="dash-kind">
                    <span className="dash-swatch" style={{ background: group.color }} aria-hidden="true" />
                    {group.label}
                  </span>
                  {s.room && (
                    <span className="dash-room">
                      <MapPin size={13} aria-hidden="true" />
                      {s.room}
                    </span>
                  )}
                </p>
              </div>
            </li>
          )
        })}
      </ol>
      {more > 0 && (
        <p className="dash-more">
          {more} more {more === 1 ? 'session starts' : 'sessions start'} before {until}.
        </p>
      )}
    </>
  )
}
