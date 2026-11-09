import { useCallback, useMemo, useState, type ReactNode } from 'react'
import { useSearchParams } from 'react-router'
import SessionDrawer from './SessionDrawer.tsx'
import { SessionDrawerContext, type SessionDrawerApi } from './context.ts'

export const SESSION_PARAM = 'session'

/**
 * Holds the session drawer for the whole app. The open session lives in the URL (`?session=<id>`), so a link or
 * a reload opens the same drawer; the in-drawer history (Similar sessions, a speaker's other talks) is kept here
 * so Back returns to the previous session. A URL that names a session the history does not end with (a deep
 * link, or a page changing it) starts a fresh history.
 */
export default function SessionDrawerProvider({ children }: { children: ReactNode }) {
  const [params, setParams] = useSearchParams()
  const [history, setHistory] = useState<string[]>([])
  const [agendaVersion, setAgendaVersion] = useState(0)
  const current = params.get(SESSION_PARAM)
  const stack = useMemo(
    () => (!current ? [] : history[history.length - 1] === current ? history : [current]),
    [current, history],
  )

  const show = useCallback(
    (next: string[]) => {
      setHistory(next)
      const id = next[next.length - 1]
      setParams(
        (prev) => {
          const p = new URLSearchParams(prev)
          if (id) p.set(SESSION_PARAM, id)
          else p.delete(SESSION_PARAM)
          return p
        },
        { replace: true },
      )
    },
    [setParams],
  )

  const api: SessionDrawerApi = useMemo(
    () => ({ open: (id: string) => show([id]), agendaVersion }),
    [show, agendaVersion],
  )

  return (
    <SessionDrawerContext.Provider value={api}>
      {children}
      <SessionDrawer
        sessionId={current}
        canGoBack={stack.length > 1}
        onNavigate={(id) => show([...stack, id])}
        onBack={() => show(stack.slice(0, -1))}
        onClose={() => show([])}
        onAgendaChanged={() => setAgendaVersion((v) => v + 1)}
      />
    </SessionDrawerContext.Provider>
  )
}
