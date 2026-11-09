import { ChevronRight } from 'lucide-react'
import { formatWhen, placeName } from '../ask/chat.ts'
import SampleLabel from './SampleLabel.tsx'

export type Talk = {
  id: string
  title: string
  starts_at: string | null
  ends_at: string | null
  room: string | null
  speakers: string[]
  sample: boolean
}

type Props = { talks: Talk[]; selected: string | null; onSelect: (id: string) => void }

export default function TalkList({ talks, selected, onSelect }: Props) {
  return (
    <ul className="catchup-list" aria-label="Talks you can catch up on">
      {talks.map((t) => (
        <li key={t.id}>
          <button
            type="button"
            className="catchup-talk"
            aria-current={t.id === selected ? 'true' : undefined}
            onClick={() => onSelect(t.id)}
          >
            <span className="catchup-talk-body">
              <span className="catchup-talk-title">{t.title}</span>
              <span className="catchup-talk-meta">
                {formatWhen(t.starts_at)} · {placeName(t.room)}
              </span>
              {t.speakers.length > 0 && <span className="catchup-talk-meta">{t.speakers.join(', ')}</span>}
              {t.sample && <SampleLabel />}
            </span>
            <ChevronRight size={18} aria-hidden="true" className="catchup-talk-chevron" />
          </button>
        </li>
      ))}
    </ul>
  )
}
