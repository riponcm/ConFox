// Shapes returned by /api/groups. Kept with the feature so parallel pages do not share one types file.
import type { Slot } from '../connect/types.ts'

export type Basis = 'school' | 'country' | 'company' | 'community' | 'interest'

export type GroupSlot = {
  session_id: string
  title: string
  starts_at: string
  ends_at: string
  room?: string | null
}

/** A proposed time with its votes, as one user sees it. */
export type TallySlot = GroupSlot & { votes: number; voted: boolean }

export type Group = {
  id: string
  title: string
  basis: Basis
  value: string
  description: string
  host_id: string
  host_name: string
  members: string[]
  member_names: string[]
  max_members: number
  proposed_slots: GroupSlot[]
  fixed_slot: GroupSlot | null
  status: 'open' | 'fixed'
  created_at: string
  sample: boolean
  member_count: number
  spots_left: number
  is_member: boolean
  /** After fix: members not given the meetup because they were busy then. */
  busy_members?: string[]
  is_host: boolean
  /** Why the group is relevant to the user ("You studied at University of Utah"), if it is. */
  match: { basis: Basis; value: string; label: string } | null
  tally: TallySlot[]
  /** session_id of the time with most votes, or null when nobody has voted. */
  leading: string | null
}

/** GET /api/groups */
export type GroupsResponse = { groups: Group[]; mine: Group[] }

/** GET /api/groups/suggest: a value the user shares and how many people here share it. */
export type Suggestion = {
  basis: Basis
  value: string
  count: number
  label: string
  title: string
  /** Ids of open groups already formed around this value. */
  existing: string[]
}

export type SuggestResponse = { suggestions: Suggestion[] }

/** What the Propose dialog opens with. */
export type ProposeSeed = { basis: Basis; value: string; title?: string }

export type SlotsResponse = { slots: Slot[] }

/** A hallway board post (GET /api/groups/board). */
export type BoardPost = {
  kind: 'post'
  id: string
  text: string
  place: string
  tags: string[]
  author_id: string
  author_name: string
  created_at: string
  expires_at: string
  sample: boolean
  /** Tags matching the viewer's interests; for_you when there is at least one. */
  matching: string[]
  for_you: boolean
  mine: boolean
}

/** A meetup group as it appears in the board feed. */
export type BoardGroup = {
  kind: 'group'
  id: string
  title: string
  basis: Basis
  value: string
  status: 'open' | 'fixed'
  fixed_slot: GroupSlot | null
  member_count: number
  author_name: string
  created_at: string
  for_you: boolean
  is_member: boolean
  sample: boolean
}

export type BoardResponse = { items: (BoardPost | BoardGroup)[]; interests: string[]; minutes: number[] }
