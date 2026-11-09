// The signed-in user's profile (generated sample data for the demo user; labelled as such in the UI).
import { createContext, useContext } from 'react'

export type Visibility = 'public' | 'private'

/** The fields the profile editor can change; the API refuses anything else. */
export type ProfileFields = {
  name: string
  title: string
  company: string
  city: string
  country: string
  bio: string
  interests: string[]
  projects: string[]
  tracks: string[]
  schools: string[]
  past_companies: string[]
  communities: string[]
  looking_for: string
  links: string[]
  visibility: Visibility
}

export type Profile = ProfileFields & {
  id: string
  kind?: string
  sample?: boolean
  updated_at?: string | null
  has_embedding: boolean
}

export type ProfileOptions = Record<
  'interests' | 'projects' | 'tracks' | 'schools' | 'companies' | 'communities' | 'cities' | 'countries',
  string[]
>

export type SaveResponse = {
  profile: Profile
  changed: string[]
  embedding: 'updated' | 'unchanged' | 'skipped' | 'failed'
  note: string
}

/** Limits the API enforces; the form mirrors them so most mistakes never leave the browser. */
export const LIMITS = { name: 80, short: 80, bio: 500, lookingFor: 200, phrase: 40, interests: 12, projects: 20, links: 3 }

/** Shown until the API answers, so the top bar never flashes empty. */
export const FALLBACK_NAME = 'Emma'

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  return (parts[0]?.[0] ?? '?').toUpperCase()
}

export function firstName(name: string): string {
  return name.trim().split(/\s+/)[0] || FALLBACK_NAME
}

export type ProfileState = {
  profile: Profile | null
  /** Bumped after every save; pages put it in their fetch dependencies so they reload against the new profile. */
  version: number
  openEditor: () => void
}

export const ProfileContext = createContext<ProfileState>({ profile: null, version: 0, openEditor: () => {} })

export function useProfile(): ProfileState {
  return useContext(ProfileContext)
}

/** Shortcut for pages that only need to refetch after a save. */
export function useProfileVersion(): number {
  return useContext(ProfileContext).version
}
