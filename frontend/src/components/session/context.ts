import { createContext, useContext } from 'react'

/** What the session drawer offers to every page (mounted once in the Shell). */
export type SessionDrawerApi = {
  /** Open the drawer on a session, starting a fresh in-drawer history. */
  open: (sessionId: string) => void
  /** Bumped whenever the drawer changes the agenda, so pages showing agenda state can reload. */
  agendaVersion: number
}

export const SessionDrawerContext = createContext<SessionDrawerApi | null>(null)

/** The drawer, or null when rendered outside the Shell (titles then stay plain text). */
export function useSessionDrawer(): SessionDrawerApi | null {
  return useContext(SessionDrawerContext)
}

/** 0 outside the Shell; use as an effect dependency to reload after an agenda change in the drawer. */
export function useAgendaVersion(): number {
  return useContext(SessionDrawerContext)?.agendaVersion ?? 0
}
