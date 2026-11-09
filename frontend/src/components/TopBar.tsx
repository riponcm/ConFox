import { Link } from 'react-router'
import { FALLBACK_NAME, firstName, initials, useProfile } from '../profile.ts'
import FoxMark from './FoxMark.tsx'

type Props = { profileOpen: boolean; onOpenProfile: () => void }

export default function TopBar({ profileOpen, onOpenProfile }: Props) {
  const { profile } = useProfile()
  const name = profile?.name ?? FALLBACK_NAME
  return (
    <header className="topbar">
      <Link to="/" className="brand" aria-label="Confox home">
        <FoxMark />
        <span className="brand-name">Confox</span>
        <span className="brand-sub">KubeCon NA 2026</span>
      </Link>
      <button
        type="button"
        className="user-button"
        onClick={onOpenProfile}
        aria-haspopup="dialog"
        aria-expanded={profileOpen}
        aria-label={`Edit profile for ${name}`}
      >
        <span className="avatar" aria-hidden="true">{initials(name)}</span>
        <span className="user-name">{firstName(name)}</span>
      </button>
    </header>
  )
}
