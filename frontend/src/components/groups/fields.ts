import type { LucideIcon } from 'lucide-react'
import { Building2, GraduationCap, Globe, Sparkles, Users } from 'lucide-react'
import type { WhyField } from '../people/types.ts'
import type { Basis } from './types.ts'

export const BASES: Basis[] = ['school', 'country', 'community', 'company', 'interest']

export const BASIS_LABEL: Record<Basis, string> = {
  school: 'School',
  country: 'Country',
  community: 'Community',
  company: 'Company',
  interest: 'Interest',
}

export const BASIS_ICON: Record<Basis, LucideIcon> = {
  school: GraduationCap,
  country: Globe,
  community: Users,
  company: Building2,
  interest: Sparkles,
}

/** Match reasons that can seed a meetup; city and bio mentions cannot. */
export const WHY_BASIS: Partial<Record<WhyField, Basis>> = {
  schools: 'school',
  communities: 'community',
  company: 'company',
  interests: 'interest',
}

/** The default title for a meetup around one value, as the API names it. */
export function defaultTitle(basis: Basis, value: string): string {
  if (basis === 'school') return `${value} alumni meetup`
  if (basis === 'company') return `${value} folks meetup`
  return `${value} meetup`
}
