import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'
import { getJSON } from '../api.ts'
import TalkDetail from '../components/catchup/TalkDetail.tsx'
import TalkList, { type Talk } from '../components/catchup/TalkList.tsx'
import '../styles/ask.css'
import '../styles/catchup.css'

export default function CatchUp() {
  const [talks, setTalks] = useState<Talk[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [params, setParams] = useSearchParams()
  const selected = params.get('talk')

  useEffect(() => {
    getJSON<Talk[]>('catchup')
      .then(setTalks)
      .catch((e: Error) => setError(e.message))
  }, [])

  const select = (id: string | null) => setParams(id ? { talk: id } : {})

  return (
    <section className="page catchup-page" aria-labelledby="page-title">
      <h1 id="page-title">Catch up</h1>
      {selected ? (
        <TalkDetail key={selected} id={selected} onBack={() => select(null)} />
      ) : (
        <>
          <p className="page-lead">
            Missed a keynote? Read a short summary, the key takeaways and the transcript, then ask questions about it.
          </p>
          <p className="catchup-note">
            Recordings are not public yet, so these transcripts are generated samples written from each talk's public
            description.
          </p>
          {error && <p className="chat-error">Could not load talks ({error}).</p>}
          {talks && talks.length === 0 && <p className="catchup-note">No transcripts are loaded yet.</p>}
          {talks && talks.length > 0 && <TalkList talks={talks} selected={selected} onSelect={select} />}
        </>
      )}
    </section>
  )
}
