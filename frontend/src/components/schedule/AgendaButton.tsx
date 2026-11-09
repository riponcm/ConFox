import { useState } from 'react'
import { CalendarPlus, Check } from 'lucide-react'

type Props = {
  title: string
  on: boolean
  /** Adds or removes the session; resolves once the page has the new state. */
  onToggle: () => Promise<void>
}

/** Add to agenda: outlined "Agenda" when off, filled "Added" when on. Disabled while the change is saving. */
export default function AgendaButton({ title, on, onToggle }: Props) {
  const [busy, setBusy] = useState(false)
  const click = () => {
    setBusy(true)
    onToggle().finally(() => setBusy(false))
  }
  return (
    <button
      type="button"
      className={on ? 'agenda-btn is-on' : 'agenda-btn'}
      aria-pressed={on}
      aria-label={on ? `Added to agenda: ${title}` : `Agenda: add ${title}`}
      title={on ? 'On your agenda. Click to remove' : 'Add to your agenda'}
      disabled={busy}
      aria-busy={busy}
      onClick={click}
    >
      {on ? <Check size={14} aria-hidden="true" /> : <CalendarPlus size={14} aria-hidden="true" />}
      <span>{on ? 'Added' : 'Agenda'}</span>
    </button>
  )
}
