import { useEffect } from 'react'
import { CircleCheck, X } from 'lucide-react'

type Props = { text: string; onDone: () => void; ms?: number }

/** A short confirmation at the bottom of the screen. The live region announces it; it leaves on its own. */
export default function Toast({ text, onDone, ms = 4500 }: Props) {
  useEffect(() => {
    const t = setTimeout(onDone, ms)
    return () => clearTimeout(t)
  }, [onDone, ms])

  return (
    <div className="toast" role="status" aria-live="polite">
      <CircleCheck size={18} aria-hidden="true" className="toast-icon" />
      <span className="toast-text">{text}</span>
      <button type="button" className="icon-button toast-close" aria-label="Dismiss" onClick={onDone}>
        <X size={16} aria-hidden="true" />
      </button>
    </div>
  )
}
