import { useCallback, useEffect, useState } from 'react'
import { LoaderCircle, Plus, Users } from 'lucide-react'
import { getJSON } from '../../api.ts'
import { BASIS_ICON } from './fields.ts'
import GroupCard from './GroupCard.tsx'
import HallwayBoard from './HallwayBoard.tsx'
import ProposeDialog from './ProposeDialog.tsx'
import type { Group, GroupsResponse, ProposeSeed, SuggestResponse, Suggestion } from './types.ts'

type Props = {
  userId: string
  /** A meetup to propose, handed over from a Match card: the dialog opens with it when the tab mounts. */
  seed: ProposeSeed | null
}

type Load = { status: 'loading' } | { status: 'failed' } | { status: 'ready'; data: GroupsResponse }

export default function GroupsTab({ userId, seed }: Props) {
  const [load, setLoad] = useState<Load>({ status: 'loading' })
  const [suggested, setSuggested] = useState<Suggestion[]>([])
  const [dialog, setDialog] = useState<ProposeSeed | null>(seed)
  const [said, setSaid] = useState('')
  const [version, setVersion] = useState(0)

  const reload = useCallback(
    (signal?: AbortSignal) =>
      Promise.all([
        getJSON<GroupsResponse>('groups', { user_id: userId }, { signal }),
        getJSON<SuggestResponse>('groups/suggest', { user_id: userId }, { signal }),
      ])
        .then(([data, s]) => {
          setLoad({ status: 'ready', data })
          setSuggested(s.suggestions)
        })
        .catch((err: unknown) => {
          if (signal?.aborted) return
          console.error('groups failed', err)
          setLoad((l) => (l.status === 'ready' ? l : { status: 'failed' }))
        }),
    [userId],
  )

  useEffect(() => {
    const ctrl = new AbortController()
    reload(ctrl.signal)
    return () => ctrl.abort()
  }, [reload])

  const changed = (_g: Group, sentence: string) => {
    setSaid(sentence)
    setVersion((v) => v + 1)
    reload()
  }

  const created = (g: Group) => {
    setDialog(null)
    setSaid(`Proposed ${g.title}. It is under Your groups; fix a time once people have voted.`)
    setVersion((v) => v + 1)
    reload()
  }

  const titleOf = new Map(
    load.status === 'ready' ? [...load.data.groups, ...load.data.mine].map((g) => [g.id, g.title]) : [],
  )

  return (
    <div className="groups-tab">
      <p className="people-note">Sample groups and their members are generated demo data; groups you create are real.</p>
      <p className="people-sr-only" role="status" aria-live="polite">
        {said}
      </p>
      {said && (
        <p className="group-said" aria-hidden="true">
          {said}
        </p>
      )}

      <section aria-labelledby="groups-suggested">
        <div className="group-section-head">
          <h2 id="groups-suggested" className="section-label">
            Suggested for you
          </h2>
          <button type="button" className="group-btn" onClick={() => setDialog({ basis: 'interest', value: '' })}>
            <Plus size={14} aria-hidden="true" />
            Propose meetup
          </button>
        </div>
        {suggested.length === 0 && load.status === 'ready' && (
          <p className="group-empty">No shared schools, places or communities found yet.</p>
        )}
        <ul className="suggest-list">
          {suggested.map((s) => {
            const Icon = BASIS_ICON[s.basis]
            const open = s.existing.map((id) => titleOf.get(id)).filter(Boolean)
            return (
              <li key={`${s.basis}:${s.value}`}>
                <button
                  type="button"
                  className="suggest-card"
                  onClick={() => setDialog({ basis: s.basis, value: s.value, title: s.title })}
                >
                  <Icon size={16} aria-hidden="true" className="suggest-icon" />
                  <span className="suggest-body">
                    <span className="suggest-title">Propose a meetup for {s.value}</span>
                    <span className="suggest-meta">
                      {s.count} {s.count === 1 ? 'person' : 'people'} here
                      {open.length > 0 && ` · ${open.length} open group${open.length > 1 ? 's' : ''} below`}
                    </span>
                  </span>
                  <Plus size={16} aria-hidden="true" className="suggest-plus" />
                </button>
              </li>
            )
          })}
        </ul>
      </section>

      {load.status === 'loading' && (
        <p className="people-status">
          <LoaderCircle size={18} className="spin" aria-hidden="true" />
          Loading groups…
        </p>
      )}
      {load.status === 'failed' && (
        <p className="people-status">Could not load groups. Check that the API is running and try again.</p>
      )}

      {load.status === 'ready' && (
        <>
          <section aria-labelledby="groups-join">
            <h2 id="groups-join" className="section-label group-section-label">
              Groups you can join
            </h2>
            {load.data.groups.length === 0 ? (
              <p className="group-empty">No other groups yet.</p>
            ) : (
              <ul className="group-list">
                {load.data.groups.map((g) => (
                  <li key={g.id}>
                    <GroupCard group={g} userId={userId} onChanged={changed} />
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section aria-labelledby="groups-mine">
            <h2 id="groups-mine" className="section-label group-section-label">
              Your groups
            </h2>
            {load.data.mine.length === 0 ? (
              <p className="group-empty">
                <Users size={15} aria-hidden="true" /> You have not joined a group yet. Join one above or propose your own.
              </p>
            ) : (
              <ul className="group-list">
                {load.data.mine.map((g) => (
                  <li key={g.id}>
                    <GroupCard group={g} userId={userId} onChanged={changed} />
                  </li>
                ))}
              </ul>
            )}
          </section>

        </>
      )}

      <HallwayBoard userId={userId} version={version} />

      <ProposeDialog userId={userId} seed={dialog} onClose={() => setDialog(null)} onCreated={created} />
    </div>
  )
}
