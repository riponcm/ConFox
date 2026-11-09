import type { ReactNode } from 'react'
import { useSessionDrawer } from './context.ts'

type Props = { id: string; children: ReactNode; className?: string }

/** A session title that opens the session drawer. Outside the Shell it is plain text. */
export default function SessionLink({ id, children, className }: Props) {
  const drawer = useSessionDrawer()
  if (!drawer || !id) return <span className={className}>{children}</span>
  return (
    <button
      type="button"
      className={className ? `session-link ${className}` : 'session-link'}
      aria-haspopup="dialog"
      onClick={() => drawer.open(id)}
    >
      {children}
    </button>
  )
}
