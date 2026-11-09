import {
  Building2,
  CalendarDays,
  Coffee,
  GitPullRequest,
  GraduationCap,
  Mic,
  Pause,
  Presentation,
  StickyNote,
  Store,
  Zap,
  type LucideIcon,
} from 'lucide-react'
import { kindLabel } from './time.ts'

const ICONS: Record<string, LucideIcon> = {
  keynote: Mic,
  talk: Presentation,
  lightning: Zap,
  tutorial: GraduationCap,
  contribfest: GitPullRequest,
  poster: StickyNote,
  showcase: Store,
  colocated: Building2,
  break: Pause,
}

/** The session kind as a small icon with an accessible name ("Lightning talk"). */
export default function KindIcon({ kind, isFood, size = 14 }: { kind: string; isFood?: boolean; size?: number }) {
  const Icon = kind === 'break' && isFood ? Coffee : (ICONS[kind] ?? CalendarDays)
  const label = kindLabel(kind, isFood)
  return (
    <span className="sch-kind" role="img" aria-label={label} title={label}>
      <Icon size={size} aria-hidden="true" />
    </span>
  )
}
