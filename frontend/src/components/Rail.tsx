import { useEffect, useRef, useState } from 'react'
import { Ellipsis } from 'lucide-react'
import { NavLink, useLocation } from 'react-router'
import { PRIMARY_NAV, SECONDARY_NAV, type NavItem } from '../nav.ts'

function RailLink({ item, onNavigate }: { item: NavItem; onNavigate?: () => void }) {
  const Icon = item.icon
  return (
    <NavLink to={item.to} end className="rail-link" onClick={onNavigate}>
      <Icon size={18} aria-hidden="true" />
      <span className="rail-label">{item.label}</span>
    </NavLink>
  )
}

// Phone only: the items after the divider live in a small menu.
function MoreMenu() {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const { pathname } = useLocation()
  const active = SECONDARY_NAV.some((item) => item.to === pathname)

  useEffect(() => {
    if (!open) return
    const onPointerDown = (e: PointerEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  return (
    <div className="rail-more" ref={ref}>
      <button
        type="button"
        className={active ? 'rail-link is-active' : 'rail-link'}
        aria-expanded={open}
        aria-controls="more-menu"
        onClick={() => setOpen((v) => !v)}
      >
        <Ellipsis size={18} aria-hidden="true" />
        <span className="rail-label">More</span>
      </button>
      {open && (
        <ul id="more-menu" className="more-menu">
          {SECONDARY_NAV.map((item) => (
            <li key={item.to}>
              <RailLink item={item} onNavigate={() => setOpen(false)} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function Rail() {
  return (
    <nav className="rail" aria-label="Main">
      <ul className="rail-list rail-primary">
        {PRIMARY_NAV.map((item) => (
          <li key={item.to}>
            <RailLink item={item} />
          </li>
        ))}
      </ul>
      <hr className="rail-divider" />
      <ul className="rail-list rail-secondary">
        {SECONDARY_NAV.map((item) => (
          <li key={item.to}>
            <RailLink item={item} />
          </li>
        ))}
      </ul>
      <MoreMenu />
    </nav>
  )
}
