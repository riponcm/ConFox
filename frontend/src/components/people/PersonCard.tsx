import Avatar from './Avatar.tsx'
import { whyIcon } from './fields.ts'
import type { MatchResult, Why } from './types.ts'

type Props = { person: MatchResult; onWhy: (why: Why) => void }

export default function PersonCard({ person, onWhy }: Props) {
  const role = [person.title, person.company].filter(Boolean).join(' · ')
  return (
    <article className="person-card" aria-labelledby={`person-${person.id}`}>
      <Avatar name={person.name} picture={person.picture} />
      <div className="person-body">
        <div className="person-head">
          <h2 id={`person-${person.id}`} className="person-name">{person.name}</h2>
          {person.sample && (
            <span className="chip chip-warn person-sample" title="Generated sample attendee, not a real person">
              Sample
            </span>
          )}
        </div>
        {role && <p className="person-role">{role}</p>}
        {person.bio && <p className="person-bio">{person.bio}</p>}
        {person.why.length > 0 && (
          <ul className="person-why" aria-label={`Why ${person.name} matches`}>
            {person.why.map((w) => {
              const Icon = whyIcon(w.field)
              return (
                <li key={`${w.field}:${w.value}`}>
                  <button
                    type="button"
                    className="why-chip"
                    onClick={() => onWhy(w)}
                    title={w.field === 'q' ? `Search for ${w.value}` : `Show only people matching ${w.value}`}
                  >
                    <Icon size={13} aria-hidden="true" />
                    <span>{w.label}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </article>
  )
}
