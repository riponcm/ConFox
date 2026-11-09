import { useEffect, useRef } from 'react'
import { RefreshCw, X } from 'lucide-react'
import type { Profile, SaveResponse } from '../profile.ts'
import ProfileForm from './profile/ProfileForm.tsx'
import '../styles/profile.css'

type Props = {
  open: boolean
  profile: Profile | null
  failed: boolean
  onRetry: () => void
  onClose: () => void
  onSaved: (res: SaveResponse) => void
}

// A native modal dialog gives focus trapping, Escape to close and focus return for free.
export default function ProfileDrawer({ open, profile, failed, onRetry, onClose, onSaved }: Props) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  const close = () => ref.current?.close()

  return (
    <dialog
      ref={ref}
      className="drawer profile-drawer"
      aria-labelledby="profile-drawer-title"
      onClose={onClose}
      onClick={(e) => {
        // The body fills the dialog, so a click on the dialog itself is a backdrop click.
        if (e.target === e.currentTarget) close()
      }}
    >
      <div className="drawer-body">
        <div className="drawer-head">
          <h2 id="profile-drawer-title">Your profile</h2>
          <button type="button" className="icon-button" aria-label="Close profile" onClick={close}>
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        {/* Mounted only while open, so every opening starts from the saved profile. */}
        {open && profile && <ProfileForm profile={profile} onSaved={onSaved} onCancel={close} />}
        {open && !profile && !failed && <p className="pf-hint">Loading your profile&hellip;</p>}
        {open && !profile && failed && (
          <div className="pf-alert" role="alert">
            <p>Could not load your profile. Is the API running?</p>
            <button type="button" className="pf-secondary" onClick={onRetry}>
              <RefreshCw size={15} aria-hidden="true" /> Try again
            </button>
          </div>
        )}
      </div>
    </dialog>
  )
}
