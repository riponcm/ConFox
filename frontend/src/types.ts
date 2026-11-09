export type SessionKind =
  | 'keynote'
  | 'talk'
  | 'lightning'
  | 'tutorial'
  | 'contribfest'
  | 'poster'
  | 'showcase'
  | 'colocated'
  | 'break'
  | 'registration'

export type Session = {
  id: string
  title: string
  description?: string
  starts_at: string
  ends_at: string
  day: string
  minutes: number
  kind: SessionKind
  is_food: boolean
  track: string | null
  level: string | null
  projects: string[]
  room: string
  venue: string
  speaker_names: string[]
  companies: string[]
}
