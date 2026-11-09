import { Fragment, useState, type ReactNode } from 'react'
import { ChevronDown, ChevronRight, CircleCheck, Columns3 } from 'lucide-react'
import CompareDialog from './CompareDialog.tsx'
import { MeetingRow, ScheduleRow } from './ScheduleRow.tsx'
import type { ToggleAgenda } from './agenda.ts'
import { sortSessions, type Sort } from './filters.ts'
import { buildSegments, byStart, nowIndex, type Entry } from './segments.ts'
import { durationMin, hhmm } from './time.ts'
import type { DayResponse, ScheduleSession } from './types.ts'

type Props = { data: DayResponse; forYouOnly: boolean; sort?: Sort; onToggleAgenda?: ToggleAgenda }
type Compare = (start: string, ids: string[]) => void
type RowProps = { muted?: boolean; onToggleAgenda?: ToggleAgenda }

const NOT_FOR_YOU = 'not matching your interests'

function EntryRow({ entry, muted, onToggleAgenda }: RowProps & { entry: Entry }) {
  return entry.type === 'meeting' ? (
    <MeetingRow item={entry.item} />
  ) : (
    <ScheduleRow session={entry.session} muted={muted} onToggleAgenda={onToggleAgenda} />
  )
}

const entryMinutes = (e: Entry) => durationMin(e.type === 'meeting' ? e.item : e.session)

/** "240 min" when everything in the slot lasts as long, else "5–510 min". */
function durationLabel(entries: Entry[]): { short: number; long: number } {
  const all = entries.map(entryMinutes)
  return { short: Math.min(...all), long: Math.max(...all) }
}

function SlotHead({ start, sessions, onCompare }: { start: string; sessions: ScheduleSession[]; onCompare: Compare }) {
  const onAgenda = sessions.filter((s) => s.on_agenda).length
  return (
    <div className="sch-slot-head">
      <p className="sch-slot-text">
        <span>{sessions.length} in parallel</span>
        {onAgenda > 0 && <span>{onAgenda} on your agenda</span>}
      </p>
      {onAgenda > 0 && (
        <span className="chip chip-ok">
          <CircleCheck size={12} aria-hidden="true" />
          decided
        </span>
      )}
      <button
        type="button"
        className="sch-ghost-btn"
        aria-haspopup="dialog"
        onClick={() =>
          onCompare(
            start,
            sessions.map((s) => s.id),
          )
        }
      >
        <Columns3 size={14} aria-hidden="true" />
        Compare
      </button>
    </div>
  )
}

function Block({
  start,
  entries,
  muted,
  onToggleAgenda,
  onCompare,
}: RowProps & { start: string; entries: Entry[]; onCompare?: Compare }) {
  const sessions = entries.flatMap((e) => (e.type === 'session' ? [e.session] : []))
  const { short, long } = durationLabel(entries)
  return (
    <section className="sch-block" aria-label={`From ${hhmm(start)}`}>
      <div className="sch-block-time">
        <time dateTime={start}>{hhmm(start)}</time>
        <span className="sch-block-dur">{short === long ? `${long} min` : `${short}–${long} min`}</span>
      </div>
      <div className="sch-block-main">
        {onCompare && sessions.length >= 2 && <SlotHead start={start} sessions={sessions} onCompare={onCompare} />}
        <ul className="sch-list">
          {entries.map((e) => (
            <EntryRow key={e.id} entry={e} muted={muted} onToggleAgenda={onToggleAgenda} />
          ))}
        </ul>
      </div>
    </section>
  )
}

function FoldToggle({ open, onClick, children }: { open: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button type="button" className="sch-fold-toggle" aria-expanded={open} onClick={onClick}>
      {open ? <ChevronDown size={15} aria-hidden="true" /> : <ChevronRight size={15} aria-hidden="true" />}
      <span className="sch-fold-text">{children}</span>
      <span className="sch-fold-action">{open ? 'Hide' : 'Show'}</span>
    </button>
  )
}

/** Best match or Most going: one ranked list, each row with its own time. In For you, the rest folds below. */
function Ranked({ data, forYouOnly, sort, onToggleAgenda }: Props & { sort: Sort }) {
  const [open, setOpen] = useState(false)
  const sorted = sortSessions(data.sessions, sort)
  const shown = forYouOnly ? sorted.filter((s) => s.for_you) : sorted
  const rest = forYouOnly ? sorted.filter((s) => !s.for_you) : []
  if (sorted.length === 0) return <p className="sch-empty">No sessions match these filters.</p>
  return (
    <div className="sch-day sch-ranked">
      <ul className="sch-list">
        {shown.map((s) => (
          <ScheduleRow key={s.id} session={s} showTime onToggleAgenda={onToggleAgenda} />
        ))}
      </ul>
      {rest.length > 0 && (
        <div className="sch-fold">
          <FoldToggle open={open} onClick={() => setOpen(!open)}>
            {rest.length} more {NOT_FOR_YOU}
          </FoldToggle>
          {open && (
            <ul className="sch-list">
              {rest.map((s) => (
                <ScheduleRow key={s.id} session={s} showTime muted onToggleAgenda={onToggleAgenda} />
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

export default function DayView({ data, forYouOnly, sort = 'time', onToggleAgenda }: Props) {
  const [open, setOpen] = useState<Set<string>>(new Set())
  const [compare, setCompare] = useState<{ start: string; ids: string[] } | null>(null)
  const segments = buildSegments(data, forYouOnly)
  const isToday = data.now.slice(0, 10) === data.day
  const nowAt = isToday ? nowIndex(segments, data.now) : -1
  // Read the compared sessions from the current data, so Add to agenda inside the dialog shows at once.
  const compared = compare ? data.sessions.filter((s) => compare.ids.includes(s.id)) : null

  const toggle = (key: string) =>
    setOpen((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })

  const dialog = (
    <CompareDialog
      sessions={compared}
      start={compare?.start ?? ''}
      onClose={() => setCompare(null)}
      onToggleAgenda={onToggleAgenda}
    />
  )

  if (sort !== 'time') return <Ranked data={data} forYouOnly={forYouOnly} sort={sort} onToggleAgenda={onToggleAgenda} />

  const nowLine = (
    <p className="sch-now" role="note">
      <span className="sch-now-label">
        Now <time dateTime={data.now}>{hhmm(data.now)}</time>
      </span>
    </p>
  )

  if (segments.length === 0) return <p className="sch-empty">Nothing matches on this day.</p>

  const onCompare: Compare = (start, ids) => setCompare({ start, ids })

  return (
    <div className="sch-day">
      {segments.map((seg, i) => {
        if (seg.type === 'block') {
          return (
            <Fragment key={seg.key}>
              {i === nowAt && nowLine}
              <Block start={seg.start} entries={seg.entries} onToggleAgenda={onToggleAgenda} onCompare={onCompare} />
            </Fragment>
          )
        }
        const last = seg.entries[seg.entries.length - 1].start
        const prev = segments[i - 1]
        const n = seg.entries.length
        const where =
          last !== seg.start
            ? 'in this stretch'
            : prev?.type === 'block' && prev.start === seg.start
              ? 'at this time'
              : `at ${hhmm(seg.start)}`
        return (
          <Fragment key={seg.key}>
            {i === nowAt && nowLine}
            <div className="sch-fold">
              <FoldToggle open={open.has(seg.key)} onClick={() => toggle(seg.key)}>
                {n} more {where} {NOT_FOR_YOU}
                {last !== seg.start && (
                  <span className="sch-fold-range">
                    {' '}
                    (<time dateTime={seg.start}>{hhmm(seg.start)}</time>–<time dateTime={last}>{hhmm(last)}</time>)
                  </span>
                )}
              </FoldToggle>
              {open.has(seg.key) &&
                byStart(seg.entries).map(([start, list]) => (
                  <Block key={start} start={start} entries={list} muted onToggleAgenda={onToggleAgenda} />
                ))}
            </div>
          </Fragment>
        )
      })}
      {nowAt === segments.length && nowLine}
      {dialog}
    </div>
  )
}
