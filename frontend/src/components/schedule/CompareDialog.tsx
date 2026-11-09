import { useEffect, useRef } from 'react'
import { CircleCheck, X } from 'lucide-react'
import AgendaButton from './AgendaButton.tsx'
import KindIcon from './KindIcon.tsx'
import { Duration, TimeRange } from './ScheduleRow.tsx'
import { goingTitle } from './filters.ts'
import { canAdd, type ToggleAgenda } from './agenda.ts'
import { durationMin, hhmm, roomLabel } from './time.ts'
import type { ScheduleSession } from './types.ts'

type Props = {
  /** Sessions starting together; null when closed. */
  sessions: ScheduleSession[] | null
  start: string
  onClose: () => void
  onToggleAgenda?: ToggleAgenda
}

/** Side by side comparison of sessions that start at the same time. A native modal dialog gives focus trapping,
 * Escape to close and focus return. */
export default function CompareDialog({ sessions, start, onClose, onToggleAgenda }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  const open = sessions !== null

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  const list = sessions ?? []
  return (
    <dialog
      ref={ref}
      className="sch-compare"
      aria-labelledby="sch-compare-title"
      onClose={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) ref.current?.close()
      }}
    >
      <div className="sch-compare-body">
        <div className="sch-compare-head">
          <h2 id="sch-compare-title">
            Compare {list.length} at <time dateTime={start}>{start ? hhmm(start) : ''}</time>
          </h2>
          <button type="button" className="icon-button" aria-label="Close comparison" onClick={() => ref.current?.close()}>
            <X size={18} aria-hidden="true" />
          </button>
        </div>
        <ul className="sch-compare-cols">
          {list.map((s) => {
            const why = (s.why ?? []).filter((w) => w !== 'on your agenda')
            const clashes = s.clashes ?? []
            return (
              <li key={s.id} className={s.on_agenda ? 'sch-compare-col is-agenda' : 'sch-compare-col'}>
                <p className="sch-title">
                  <KindIcon kind={s.kind} isFood={s.is_food} />
                  <span>{s.title}</span>
                </p>
                {s.on_agenda && (
                  <span className="chip chip-ok">
                    <CircleCheck size={12} aria-hidden="true" />
                    On your agenda
                  </span>
                )}
                <dl className="sch-compare-facts">
                  <dt>Time</dt>
                  <dd>
                    <TimeRange start={s.starts_at} end={s.ends_at} />
                  </dd>
                  <dt>Room</dt>
                  <dd>{roomLabel(s.room) || 'Not set'}</dd>
                  <dt>Track</dt>
                  <dd>{s.track || 'None'}</dd>
                  <dt>Level</dt>
                  <dd>{s.level || 'Any'}</dd>
                  <dt>Length</dt>
                  <dd>
                    <Duration min={durationMin(s)} />
                  </dd>
                  <dt>Why</dt>
                  <dd>{why.length ? why.join(', ') : 'Not close to your interests'}</dd>
                  <dt>Going</dt>
                  <dd>{s.going ? goingTitle(s) : 'Nobody yet'}</dd>
                  <dt>Clash</dt>
                  <dd className={clashes.length ? 'is-warn' : undefined}>
                    {clashes.length ? `Overlaps ${clashes.join(', ')}` : 'None'}
                  </dd>
                </dl>
                {onToggleAgenda && canAdd(s) && (
                  <div className="sch-compare-action">
                    <AgendaButton
                      title={s.title}
                      on={!!s.on_agenda}
                      offLabel="Add to agenda"
                      onToggle={() => onToggleAgenda(s.id, !!s.on_agenda)}
                    />
                  </div>
                )}
              </li>
            )
          })}
        </ul>
        <p className="sample-note">Going counts come from generated sample attendees.</p>
      </div>
    </dialog>
  )
}
