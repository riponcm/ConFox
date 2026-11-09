/** Breaks, food and registration are not things you add to an agenda (the API refuses them too). */
export function canAdd(session: { kind: string; is_food?: boolean }): boolean {
  return !session.is_food && session.kind !== 'break' && session.kind !== 'registration'
}

/** Adds (on = false) or removes (on = true) a session; resolves once the page shows the new state. */
export type ToggleAgenda = (sessionId: string, on: boolean) => Promise<void>
