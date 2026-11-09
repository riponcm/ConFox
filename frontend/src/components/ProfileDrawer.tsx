import { useEffect, useRef } from 'react'
import { GraduationCap, X } from 'lucide-react'
import { DEMO_PROFILE } from '../profile.ts'

type Props = { open: boolean; onClose: () => void }

// A native modal dialog gives focus trapping, Escape to close and focus return for free.
export default function ProfileDrawer({ open, onClose }: Props) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      className="drawer"
      aria-labelledby="profile-drawer-title"
      onClose={onClose}
      onClick={(e) => {
        // The body fills the dialog, so a click on the dialog itself is a backdrop click.
        if (e.target === e.currentTarget) ref.current?.close()
      }}
    >
      <div className="drawer-body">
        <div className="drawer-head">
          <h2 id="profile-drawer-title">Profile</h2>
          <button type="button" className="icon-button" aria-label="Close profile" onClick={() => ref.current?.close()}>
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        <div className="profile-id">
          <span className="avatar avatar-lg" aria-hidden="true">{DEMO_PROFILE.initials}</span>
          <div>
            <p className="profile-name">{DEMO_PROFILE.name}</p>
            <p className="profile-role">{DEMO_PROFILE.role}</p>
          </div>
        </div>

        <p className="profile-meta">
          <GraduationCap size={16} aria-hidden="true" />
          {DEMO_PROFILE.school}
        </p>

        <section aria-labelledby="profile-interests">
          <h3 id="profile-interests" className="section-label">Interests</h3>
          <ul className="chips">
            {DEMO_PROFILE.interests.map((interest) => (
              <li key={interest} className="chip">{interest}</li>
            ))}
          </ul>
        </section>

        <div>
          <span className="chip chip-warn">Sample profile</span>
          <p className="sample-note">Generated demo data. The demo user is signed in by default.</p>
        </div>
      </div>
    </dialog>
  )
}
