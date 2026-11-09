import { useOutletContext } from 'react-router'

/** What the shell hands to pages through the router outlet. */
export type ShellContext = { openProfile: () => void }

/** Opens the profile drawer; undefined when a page is rendered outside the shell. */
export function useOpenProfile(): (() => void) | undefined {
  return useOutletContext<ShellContext | undefined>()?.openProfile
}
