import { Sparkles } from 'lucide-react'

type Props = {
  interests: string[]
  selected: string[]
  onToggle: (interest: string) => void
  onEdit?: () => void
}

/** The profile's interests and projects as keyword filters: sessions whose title, track, projects or
 * description mention a chosen one. */
export default function InterestChips({ interests, selected, onToggle, onEdit }: Props) {
  if (!interests.length) return null
  return (
    <div className="sch-interests">
      <ul className="sch-interest-list" aria-label="Filter by your interests">
        {interests.map((i) => (
          <li key={i}>
            <button
              type="button"
              className="sch-interest"
              aria-pressed={selected.includes(i)}
              onClick={() => onToggle(i)}
            >
              <Sparkles size={13} aria-hidden="true" />
              {i}
            </button>
          </li>
        ))}
      </ul>
      <p className="sch-interest-source">
        From your profile
        {onEdit && (
          <>
            {' '}
            &middot;{' '}
            <button type="button" className="sch-link" onClick={onEdit}>
              edit
            </button>
          </>
        )}
      </p>
    </div>
  )
}
