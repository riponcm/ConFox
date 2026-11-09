import type { LucideIcon } from 'lucide-react'
import { CalendarDays, Clock, FileText, History, LayoutDashboard, MessageCircle, Users } from 'lucide-react'

export type NavItem = { to: string; label: string; icon: LucideIcon }

// Rail order is part of the design: primary items, a divider, then secondary items.
export const PRIMARY_NAV: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/now', label: 'Now', icon: Clock },
  { to: '/schedule', label: 'Schedule', icon: CalendarDays },
  { to: '/people', label: 'People', icon: Users },
]

export const SECONDARY_NAV: NavItem[] = [
  { to: '/brief', label: 'My brief', icon: FileText },
  { to: '/catch-up', label: 'Catch up', icon: History },
  { to: '/ask', label: 'Ask', icon: MessageCircle },
]
