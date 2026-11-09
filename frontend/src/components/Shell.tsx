import { useCallback, useEffect, useMemo, useState } from 'react'
import { Outlet } from 'react-router'
import { DEMO_USER, getJSON } from '../api.ts'
import { ProfileContext, type Profile, type SaveResponse } from '../profile.ts'
import ProfileDrawer from './ProfileDrawer.tsx'
import Rail from './Rail.tsx'
import SessionDrawerProvider from './session/SessionDrawerProvider.tsx'
import type { ShellContext } from './shellContext.ts'
import Toast from './Toast.tsx'
import TopBar from './TopBar.tsx'

export default function Shell() {
  const [profileOpen, setProfileOpen] = useState(false)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [profileFailed, setProfileFailed] = useState(false)
  const [version, setVersion] = useState(0)
  const [toast, setToast] = useState<{ id: number; text: string } | null>(null)

  const loadProfile = useCallback(() => {
    getJSON<Profile>(`profile/${DEMO_USER}`)
      .then((p) => {
        setProfile(p)
        setProfileFailed(false)
      })
      .catch((err: unknown) => {
        console.warn('profile failed to load', err)
        setProfileFailed(true)
      })
  }, [])

  useEffect(loadProfile, [loadProfile])

  const openEditor = useCallback(() => setProfileOpen(true), [])
  const ctx = useMemo(() => ({ profile, version, openEditor }), [profile, version, openEditor])
  // Pages reached through the router (Schedule's "edit" link) open the same editor.
  const outlet: ShellContext = { openProfile: openEditor }

  const onSaved = (res: SaveResponse) => {
    setProfile(res.profile)
    // Every page that ranks or filters by the profile refetches when this changes.
    setVersion((v) => v + 1)
    const text = res.changed.length ? 'Profile saved · matches updated' : 'Profile saved · nothing changed'
    setToast({ id: Date.now(), text: res.note ? `${text}. ${res.note}` : text })
    setProfileOpen(false)
  }

  return (
    <ProfileContext.Provider value={ctx}>
      <div className="shell">
        <a className="skip-link" href="#main">Skip to content</a>
        <TopBar profileOpen={profileOpen} onOpenProfile={openEditor} />
        <Rail />
        <SessionDrawerProvider>
          <main id="main" className="shell-main" tabIndex={-1}>
            <Outlet context={outlet} />
          </main>
        </SessionDrawerProvider>
        <ProfileDrawer
          open={profileOpen}
          profile={profile}
          failed={profileFailed}
          onRetry={loadProfile}
          onClose={() => setProfileOpen(false)}
          onSaved={onSaved}
        />
        {toast && <Toast key={toast.id} text={toast.text} onDone={() => setToast(null)} />}
      </div>
    </ProfileContext.Provider>
  )
}
