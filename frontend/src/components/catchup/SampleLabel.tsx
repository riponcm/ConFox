import { FlaskConical } from 'lucide-react'

/** Transcripts are generated stand-ins for recordings; this label must stay visible wherever they appear. */
export default function SampleLabel({ sticky = false }: { sticky?: boolean }) {
  return (
    <p className={`catchup-sample${sticky ? ' is-sticky' : ''}`}>
      <FlaskConical size={14} aria-hidden="true" /> Sample transcript (generated): not the speaker&rsquo;s actual words
    </p>
  )
}
