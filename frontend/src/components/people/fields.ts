import type { LucideIcon } from 'lucide-react'
import { Building2, GraduationCap, Globe, MapPin, Search, Sparkles, Users } from 'lucide-react'
import type { FilterKey, GroupKey, WhyField } from './types.ts'

export const FILTER_LABEL: Record<FilterKey, string> = {
  school: 'School',
  company: 'Company',
  community: 'Community',
  interest: 'Interest',
  city: 'City',
  country: 'Country',
}

export const FILTER_ICON: Record<FilterKey, LucideIcon> = {
  school: GraduationCap,
  company: Building2,
  community: Users,
  interest: Sparkles,
  city: MapPin,
  country: Globe,
}

/** Group chips in display order, each mapped to the filter it toggles. */
export const GROUP_FILTER: [GroupKey, FilterKey][] = [
  ['schools', 'school'],
  ['city', 'city'],
  ['companies', 'company'],
  ['communities', 'community'],
  ['country', 'country'],
]

/** What clicking a reason does: an exact filter, or (for `q`) a keyword search. */
export const WHY_FILTER: Record<WhyField, FilterKey | 'q'> = {
  schools: 'school',
  company: 'company',
  communities: 'community',
  city: 'city',
  interests: 'interest',
  q: 'q',
}

export function whyIcon(field: WhyField): LucideIcon {
  const target = WHY_FILTER[field]
  return target === 'q' ? Search : FILTER_ICON[target]
}
