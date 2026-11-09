import type { Ref } from 'react'
import { dayLabel, hhmm, roomLabel } from '../schedule/time.ts'
import type { Slot } from './types.ts'

type Props = {
  name: string
  legend: string
  slots: Slot[]
  /** One session id: a radio group. A list: checkboxes, for choosing several times (Groups). */
  selected: string | string[]
  /** Radio: the chosen slot. Checkboxes: the slot that was ticked or unticked. */
  onSelect: (sessionId: string) => void
  /** Checkboxes only: once this many are ticked, the others are disabled. */
  max?: number
  /** Gets the checked radio (or first checkbox), so the panel can move focus into the group when it opens. */
  checkedRef?: Ref<HTMLInputElement>
  /** Optional hint under the legend, e.g. "Pick up to 3". */
  hint?: string
}

/** Free breaks as one native radio or checkbox group: arrow keys move between radios, Tab leaves the group. */
export default function SlotList({ name, legend, slots, selected, onSelect, max, checkedRef, hint }: Props) {
  const multiple = Array.isArray(selected)
  const hintId = hint ? `${name}-hint` : undefined
  return (
    <fieldset className="slot-list" aria-describedby={hintId}>
      <legend className="slot-legend">{legend}</legend>
      {hint && (
        <p id={hintId} className="slot-hint">
          {hint}
        </p>
      )}
      {slots.map((s, i) => {
        const checked = multiple ? selected.includes(s.session_id) : s.session_id === selected
        const full = multiple && max !== undefined && !checked && selected.length >= max
        const takesFocus = multiple ? i === 0 : checked
        const room = roomLabel(s.room ?? '')
        return (
          <label key={s.session_id} className={`slot${checked ? ' is-checked' : ''}${full ? ' is-disabled' : ''}`}>
            <input
              type={multiple ? 'checkbox' : 'radio'}
              name={name}
              value={s.session_id}
              checked={checked}
              disabled={full}
              ref={takesFocus ? checkedRef : undefined}
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
