import { useId, useRef, useState, type KeyboardEvent } from 'react'
import { Plus, X } from 'lucide-react'

type Props = {
  label: string
  hint?: string
  values: string[]
  onChange: (next: string[]) => void
  suggestions?: string[]
  max: number
  maxLength: number
  placeholder?: string
  error?: string
}

const SHOWN_SUGGESTIONS = 6

/**
 * A list of short phrases as removable chips. Type and press Enter (or comma) to add, Backspace on an empty field
 * removes the last one. Suggestions come from the browser's native autocomplete list and, for touch, as a few
 * one-tap chips filtered by what is typed.
 */
export default function ChipInput({ label, hint, values, onChange, suggestions = [], max, maxLength, placeholder, error }: Props) {
  const id = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const [text, setText] = useState('')
  const [note, setNote] = useState('')
  const full = values.length >= max
  const lower = new Set(values.map((v) => v.toLowerCase()))
  const typed = text.trim().toLowerCase()
  const open = suggestions.filter((s) => !lower.has(s.toLowerCase()))
  const shown = (typed ? open.filter((s) => s.toLowerCase().includes(typed)) : open).slice(0, SHOWN_SUGGESTIONS)

  const add = (raw: string) => {
    const value = raw.trim().replace(/,+$/, '').trim()
    if (!value) return
    if (lower.has(value.toLowerCase())) {
      setNote(`${value} is already in the list`)
      setText('')
      return
    }
    if (full) {
      setNote(`At most ${max}. Remove one first.`)
      return
    }
    onChange([...values, value.slice(0, maxLength)])
    setText('')
    setNote('')
  }

  const remove = (value: string) => {
    onChange(values.filter((v) => v !== value))
    setNote(`Removed ${value}`)
    inputRef.current?.focus()
  }

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      add(text)
    } else if (e.key === 'Backspace' && text === '' && values.length > 0) {
      remove(values[values.length - 1])
    }
  }

  const describedBy = [`${id}-hint`, error ? `${id}-error` : ''].filter(Boolean).join(' ')

  return (
    <div className="pf-field" role="group" aria-labelledby={`${id}-label`}>
      <label id={`${id}-label`} htmlFor={`${id}-input`} className="pf-label">
        {label}
      </label>
      {values.length > 0 && (
        <ul className="chips pf-chips" aria-label={`${label}, ${values.length} of ${max}`}>
          {values.map((v) => (
            <li key={v} className="chip pf-chip">
              <span className="pf-chip-text">{v}</span>
              <button type="button" className="pf-chip-remove" aria-label={`Remove ${v}`} onClick={() => remove(v)}>
                <X size={13} aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="pf-chip-entry">
        <input
          ref={inputRef}
          id={`${id}-input`}
          className="pf-input"
          value={text}
          list={suggestions.length ? `${id}-list` : undefined}
          maxLength={maxLength}
          placeholder={full ? `Limit of ${max} reached` : placeholder}
          disabled={full && text === ''}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          autoComplete="off"
          enterKeyHint="enter"
          onChange={(e) => {
            const v = e.target.value
            // A comma typed or pasted at the end adds the phrase, like Enter.
            if (v.endsWith(',')) add(v)
            else setText(v)
          }}
          onKeyDown={onKey}
        />
        <button type="button" className="pf-add" onClick={() => add(text)} disabled={!text.trim()} aria-label={`Add to ${label}`}>
          <Plus size={16} aria-hidden="true" />
        </button>
        {suggestions.length > 0 && (
          <datalist id={`${id}-list`}>
            {open.map((s) => (
              <option key={s} value={s} />
            ))}
          </datalist>
        )}
      </div>
      <p id={`${id}-hint`} className="pf-hint">
        {hint ? `${hint} ` : ''}
        {values.length} of {max}.
      </p>
      {!full && shown.length > 0 && (
        <div className="pf-suggest">
          <span className="pf-suggest-label">Suggestions</span>
          <ul className="pf-suggest-list">
            {shown.map((s) => (
              <li key={s}>
                <button type="button" className="pf-suggest-chip" aria-label={`Add ${s} to ${label}`} onClick={() => add(s)}>
                  <Plus size={12} aria-hidden="true" />
                  {s}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="pf-note" aria-live="polite">
        {note}
      </p>
      {error && (
        <p id={`${id}-error`} className="pf-error">
          {error}
        </p>
      )}
    </div>
  )
}
