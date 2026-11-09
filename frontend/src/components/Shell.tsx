import { useState } from 'react'
import { Outlet } from 'react-router'
import ProfileDrawer from './ProfileDrawer.tsx'
import Rail from './Rail.tsx'
import TopBar from './TopBar.tsx'

export default function Shell() {
  const [profileOpen, setProfileOpen] = useState(false)

  return (
    <div className="shell">
      <a className="skip-link" href="#main">Skip to content</a>
      <TopBar profileOpen={profileOpen} onOpenProfile={() => setProfileOpen(true)} />
      <Rail />
      <main id="main" className="shell-main" tabIndex={-1}>
        <Outlet />
      </main>
      <ProfileDrawer open={profileOpen} onClose={() => setProfileOpen(false)} />
    </div>
  )
}
