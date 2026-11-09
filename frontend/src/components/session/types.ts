// Shape of GET /api/sessions/{id}. Kept local to the session details feature.

export type SessionListItem = {
  id: string
  title: string
  starts_at: string
  ends_at: string
  day: string
  kind: string
  is_food?: boolean
  track?: string | null
  level?: string | null
  room?: string
  on_agenda: boolean
  /** kNN similarity to the opened session (semantic list only). */
  score?: number
}

export type Speaker = {
  id: string
  name: string
  title: string
  company: string
  bio: string
  picture?: string | null
  links: { title: string; url: string }[]
  other_sessions: SessionListItem[]
}

export type WhyChip = { kind: 'interest' | 'project' | 'track' | 'similar'; label: string; value?: string; where?: string }

export type SessionDetail = {
  session: {
    id: string
    title: string
    description?: string
    starts_at: string
    ends_at: string
    day: string
    minutes?: number
    kind: string
    is_food?: boolean
    track?: string | null
    level?: string | null
    projects?: string[]
    room?: string
    venue?: string
    speaker_names?: string[]
  }
  speakers: Speaker[]
  on_agenda: boolean
  can_add: boolean
  clashes: string[]
  going: number
  going_names: string[]
  why: WhyChip[]
  similarity: { score: number; bucket: string; label: string } | null
  similar: { basis: 'semantic' | 'track' | 'none'; items: SessionListItem[] }
  same_track_later: SessionListItem[]
  catch_up: { available: boolean; chunks: number }
  slides_url: string | null
}
