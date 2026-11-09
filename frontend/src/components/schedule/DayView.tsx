import { Fragment, useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { MeetingRow, ScheduleRow } from './ScheduleRow.tsx'
import type { ToggleAgenda } from './agenda.ts'
import { buildSegments, byStart, nowIndex, type Entry } from './segments.ts'
import { hhmm } from './time.ts'
import type { DayResponse } from './types.ts'

type Props = { data: DayResponse; forYouOnly: boolean; onToggleAgenda?: ToggleAgenda }
type RowProps = { muted?: boolean; onToggleAgenda?: ToggleAgenda }

function EntryRow({ entry, muted, onToggleAgenda }: RowProps & { entry: Entry }) {
  return entry.type === 'meeting' ? (
    <MeetingRow item={entry.item} />
  ) : (
    <ScheduleRow session={entry.session} muted={muted} onToggleAgenda={onToggleAgenda} />
  )
}

function Block({ start, entries, muted, onToggleAgenda }: RowProps & { start: string; entries: Entry[] }) {
  return (
    <section className="sch-block" aria-label={`From ${hhmm(start)}`}>
      <h3 className="sch-block-time">{hhmm(start)}</h3>
      <ul className="sch-list">
        {entries.map((e) => (
          <EntryRow key={e.id} entry={e} muted={muted} onToggleAgenda={onToggleAgenda} />
        ))}
      </ul>
    </section>
  )
}

export default function DayView({ data, forYouOnly, onToggleAgenda }: Props) {
  const [open, setOpen] = useState<Set<string>>(new Set())
  const segments = buildSegments(data, forYouOnly)
  const isToday = data.now.slice(0, 10) === data.day
  const nowAt = isToday ? nowIndex(segments, data.now) : -1

  const toggle = (key: string) =>
    setOpen((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })

  const nowLine = (
    <p className="sch-now" role="note">
      <span className="sch-now-label">Now {hhmm(data.now)}</span>
    </p>
  )

  if (segments.length === 0) return <p className="sch-empty">Nothing scheduled on this day.</p>

  return (
    <div className="sch-day">
      {segments.map((seg, i) => (
        <Fragment key={seg.key}>
          {i === nowAt && nowLine}
          {seg.type === 'block' ? (
            <Block start={seg.start} entries={seg.entries} onToggleAgenda={onToggleAgenda} />
          ) : (
            <div className="sch-fold">
              <button
                type="button"
                className="sch-fold-toggle"
                aria-expanded={open.has(seg.key)}
                onClick={() => toggle(seg.key)}
              >
                {open.has(seg.key) ? (
                  <ChevronDown size={15} aria-hidden="true" />
                ) : (
                  <ChevronRight size={15} aria-hidden="true" />
                )}
                <span>
                  {seg.entries.length} more {seg.entries.length === 1 ? 'session' : 'sessions'}
                </span>
                <span className="sch-fold-range">
                  {hhmm(seg.start)}
                  {seg.entries[seg.entries.length - 1].start !== seg.start &&
                    `–${hhmm(seg.entries[seg.entries.length - 1].start)}`}
                </span>
              </button>
              {open.has(seg.key) &&
                byStart(seg.entries).map(([start, list]) => (
                  <Block key={start} start={start} entries={list} muted onToggleAgenda={onToggleAgenda} />
                ))}
            </div>
          )}
        </Fragment>
      ))}
      {nowAt === segments.length && nowLine}
    </div>
  )
}
