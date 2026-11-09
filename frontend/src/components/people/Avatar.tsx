import { useState } from 'react'

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  const first = parts[0]?.[0] ?? ''
  const last = parts.length > 1 ? parts[parts.length - 1][0] : ''
  return (first + last).toUpperCase()
}

// Speaker photos come from the public schedule; everyone else (and any broken photo) gets initials.
export default function Avatar({ name, picture }: { name: string; picture?: string | null }) {
  const [failed, setFailed] = useState(false)
  if (picture && !failed) {
    return <img className="avatar people-avatar" src={picture} alt="" loading="lazy" onError={() => setFailed(true)} />
  }
  return (
    <span className="avatar people-avatar" aria-hidden="true">
      {initials(name)}
    </span>
  )
}
