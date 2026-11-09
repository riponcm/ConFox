import { Link } from 'react-router'
import { DEMO_PROFILE } from '../profile.ts'
import FoxMark from './FoxMark.tsx'

type Props = { profileOpen: boolean; onOpenProfile: () => void }

export default function TopBar({ profileOpen, onOpenProfile }: Props) {
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
        aria-label={`Open profile for ${DEMO_PROFILE.name}`}
      >
        <span className="avatar" aria-hidden="true">{DEMO_PROFILE.initials}</span>
        <span className="user-name">{DEMO_PROFILE.name}</span>
      </button>
    </header>
  )
}
