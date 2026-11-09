import type { Ref } from 'react'
import { dayLabel, hhmm, roomLabel } from '../schedule/time.ts'
import type { Slot } from './types.ts'

type Props = {
  name: string
  legend: string
  slots: Slot[]
  selected: string
  onSelect: (sessionId: string) => void
  /** Gets the checked radio, so the panel can move focus into the group when it opens. */
  checkedRef?: Ref<HTMLInputElement>
}

/** Free breaks as one native radio group: arrow keys move between slots, Tab leaves the group. */
export default function SlotList({ name, legend, slots, selected, onSelect, checkedRef }: Props) {
  return (
    <fieldset className="slot-list">
      <legend className="slot-legend">{legend}</legend>
      {slots.map((s) => {
        const checked = s.session_id === selected
        const room = roomLabel(s.room ?? '')
        return (
          <label key={s.session_id} className={checked ? 'slot is-checked' : 'slot'}>
            <input
              type="radio"
              name={name}
              value={s.session_id}
              checked={checked}
              ref={checked ? checkedRef : undefined}
              onChange={() => onSelect(s.session_id)}
            />
            <time className="slot-time" dateTime={s.starts_at}>
              {hhmm(s.starts_at)}
            </time>
            <span className="slot-body">
              <span className="slot-title">{s.title}</span>
              <span className="slot-meta">
                {dayLabel(s.day)}
                {room && ` · ${room}`}
              </span>
            </span>
          </label>
        )
      })}
    </fieldset>
  )
}
