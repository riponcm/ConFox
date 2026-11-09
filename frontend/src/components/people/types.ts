// Shapes returned by /api/people. Kept with the feature so parallel pages do not share one types file.
export type Kind = 'attendee' | 'speaker'

/** Query parameters that act as exact filters; `interest` comes from clicking a reason. */
export type FilterKey = 'school' | 'company' | 'community' | 'interest' | 'city' | 'country'
export type Filters = Partial<Record<FilterKey, string>>

/** `field` names the profile field the reason comes from; `q` means "named in the bio", a keyword search. */
export type WhyField = 'schools' | 'company' | 'communities' | 'city' | 'country' | 'interests' | 'q'
export type Why = { label: string; field: WhyField; value: string }

export type Person = {
  id: string
  kind: Kind
  sample: boolean
  name: string
  title?: string
  company?: string
  bio?: string
  interests?: string[]
  schools?: string[]
  past_companies?: string[]
  communities?: string[]
  city?: string
  country?: string
  picture?: string | null
}

export type MatchResult = Person & { score: number; why: Why[] }

export type GroupKey = 'schools' | 'companies' | 'communities' | 'city' | 'country'
export type GroupBucket = { key: string; count: number }

export type MatchResponse = {
  results: MatchResult[]
  groups: Record<GroupKey, GroupBucket[]>
  semantic: boolean
  /** How the ranking ran: native RRF, RRF in the API, or keywords only. */
  mode?: 'hybrid' | 'hybrid-client' | 'bm25'
}
