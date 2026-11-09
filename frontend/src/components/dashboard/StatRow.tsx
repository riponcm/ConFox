import type { LucideIcon } from 'lucide-react'
import { CalendarDays, Globe, Layers, Mic, Users } from 'lucide-react'
import { type DashboardData, fmt } from './types.ts'

type Tile = { label: string; value: number; sub: string; icon: LucideIcon; sample?: boolean }

export default function StatRow({ data, dayName }: { data: DashboardData; dayName: string }) {
  const s = data.stats
  const on = data.is_today ? 'today' : `on ${dayName}`
  const tiles: Tile[] = [
    { label: `Sessions ${on}`, value: s.sessions_day, sub: `${fmt(s.sessions_total)} across the week`, icon: CalendarDays },
    { label: `Speakers ${on}`, value: s.speakers_day, sub: `${fmt(s.speakers_total)} across the week`, icon: Mic },
    { label: `Tracks ${on}`, value: s.tracks_day, sub: `${fmt(s.tracks_total)} across the week`, icon: Layers },
    { label: 'Attendees', value: s.sample_attendees, sub: 'Sample profiles', icon: Users, sample: true },
    { label: 'Countries', value: s.countries, sub: 'Among sample attendees', icon: Globe, sample: true },
  ]

  return (
    <ul className="dash-stats" aria-label="Key numbers">
      {tiles.map((t) => (
        <li key={t.label} className="dash-stat">
          <span className="dash-stat-label">
            <t.icon size={15} aria-hidden="true" />
            {t.label}
          </span>
          <span className="dash-stat-value">{fmt(t.value)}</span>
          <span className={t.sample ? 'dash-stat-sub is-sample' : 'dash-stat-sub'}>{t.sub}</span>
        </li>
      ))}
    </ul>
  )
}
