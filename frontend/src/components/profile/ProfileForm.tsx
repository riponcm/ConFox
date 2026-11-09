import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { Briefcase, Eye, GraduationCap, Link2, LoaderCircle, Save, Sparkles, Target, UserRound } from 'lucide-react'
import { ApiError, DEMO_USER, getJSON, putJSON } from '../../api.ts'
import {
  LIMITS,
  initials,
  type Profile,
  type ProfileFields,
  type ProfileOptions,
  type SaveResponse,
} from '../../profile.ts'
import ChipInput from './ChipInput.tsx'

type Props = { profile: Profile; onSaved: (res: SaveResponse) => void; onCancel: () => void }
type Errors = Partial<Record<keyof ProfileFields | 'form', string>>

const FIELDS: (keyof ProfileFields)[] = [
  'name', 'title', 'company', 'city', 'country', 'bio', 'interests', 'projects', 'tracks',
  'schools', 'past_companies', 'communities', 'looking_for', 'links', 'visibility',
]

function pick(p: ProfileFields): ProfileFields {
  return Object.fromEntries(FIELDS.map((f) => [f, p[f]])) as ProfileFields
}

/** What would be sent: trimmed text, empty link rows dropped. Also what dirty-checking compares. */
function normalise(d: ProfileFields): ProfileFields {
  const out = { ...d }
  for (const f of ['name', 'title', 'company', 'city', 'country', 'bio', 'looking_for'] as const) out[f] = d[f].trim()
  out.links = d.links.map((l) => l.trim()).filter(Boolean)
  return out
}

function isUrl(value: string): boolean {
  try {
    const u = new URL(value)
    return (u.protocol === 'http:' || u.protocol === 'https:') && u.hostname.includes('.')
  } catch {
    return false
  }
}

function validate(d: ProfileFields): Errors {
  const e: Errors = {}
  if (!d.name) e.name = 'Enter your name.'
  if (d.bio.length > LIMITS.bio) e.bio = `Keep it to ${LIMITS.bio} characters.`
  if (d.looking_for.length > LIMITS.lookingFor) e.looking_for = `Keep it to ${LIMITS.lookingFor} characters.`
  const bad = d.links.find((l) => !isUrl(l))
  if (bad) e.links = `"${bad}" is not a full web address. Start with https://`
  return e
}

/** FastAPI validation errors ({loc: ['body', field, ...], msg}) as one message per field. */
function serverErrors(detail: unknown): Errors {
  const e: Errors = {}
  if (!Array.isArray(detail)) return e
  for (const item of detail as { loc?: unknown[]; msg?: string }[]) {
    const field = item.loc?.[1]
    const key = typeof field === 'string' && (FIELDS as string[]).includes(field) ? (field as keyof ProfileFields) : 'form'
    e[key] ??= (item.msg ?? 'Not valid').replace(/^Value error, /, '')
  }
  return e
}

const EMPTY_OPTIONS: ProfileOptions = {
  interests: [], projects: [], tracks: [], schools: [], companies: [], communities: [], cities: [], countries: [],
}

export default function ProfileForm({ profile, onSaved, onCancel }: Props) {
  const id = useId()
  const formRef = useRef<HTMLFormElement>(null)
  const saved = pick(profile)
  const [draft, setDraft] = useState<ProfileFields>(() => ({ ...saved, links: [...saved.links, '', '', ''].slice(0, LIMITS.links) }))
  const [options, setOptions] = useState<ProfileOptions>(EMPTY_OPTIONS)
  const [errors, setErrors] = useState<Errors>({})
  const [saving, setSaving] = useState(false)
  const dirty = JSON.stringify(normalise(draft)) !== JSON.stringify(normalise(saved))
  const errorCount = Object.keys(errors).length

  useEffect(() => {
    const ctrl = new AbortController()
    getJSON<ProfileOptions>('profile/options', undefined, { signal: ctrl.signal })
      .then(setOptions)
      .catch((err: unknown) => !ctrl.signal.aborted && console.warn('profile suggestions failed', err))
    return () => ctrl.abort()
  }, [])

  useEffect(() => {
    // After a failed submit, move focus to the first field that needs attention.
    if (!errorCount) return
    const first = formRef.current?.querySelector<HTMLElement>('[aria-invalid="true"]')
    first?.focus()
  }, [errorCount, errors])

  const set = <K extends keyof ProfileFields>(key: K, value: ProfileFields[K]) => {
    setDraft((d) => ({ ...d, [key]: value }))
    if (errors[key])
      setErrors((prev) => {
        const next = { ...prev }
        delete next[key]
        return next
      })
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const body = normalise(draft)
    const found = validate(body)
    setErrors(found)
    if (Object.keys(found).length) return
    setSaving(true)
    try {
      onSaved(await putJSON<SaveResponse>(`profile/${DEMO_USER}`, body))
    } catch (err) {
      const fromServer = err instanceof ApiError && err.status === 422 ? serverErrors(err.detail) : {}
      setErrors(
        Object.keys(fromServer).length
          ? fromServer
          : { form: 'Could not save your profile. Check that the API is running and try again.' },
      )
      setSaving(false)
    }
  }

  const text = (key: 'name' | 'title' | 'company' | 'city' | 'country', label: string, opts: { list?: string[]; required?: boolean; autoComplete?: string } = {}) => (
    <Field id={`${id}-${key}`} label={label} error={errors[key]} required={opts.required}>
      {(props) => (
        <>
          <input
            {...props}
            className="pf-input"
            value={draft[key]}
            maxLength={LIMITS.short}
            required={opts.required}
            autoComplete={opts.autoComplete ?? 'off'}
            list={opts.list?.length ? `${id}-${key}-list` : undefined}
            onChange={(e) => set(key, e.target.value)}
          />
          {opts.list && opts.list.length > 0 && (
            <datalist id={`${id}-${key}-list`}>
              {opts.list.map((o) => <option key={o} value={o} />)}
            </datalist>
          )}
        </>
      )}
    </Field>
  )

  const trackSet = new Set(draft.tracks)
  const tracksFull = draft.tracks.length >= LIMITS.interests

  return (
    <form ref={formRef} className="pf-form" onSubmit={submit} noValidate aria-describedby={`${id}-intro`}>
      <div className="profile-id">
        <span className="avatar avatar-lg" aria-hidden="true">{initials(draft.name || profile.name)}</span>
        <div className="pf-id-text">
          <p className="profile-name">{draft.name || profile.name}</p>
          <p className="profile-role">{[draft.title, draft.company].filter(Boolean).join(' · ')}</p>
        </div>
      </div>
      <div>
        <span className="chip chip-warn">Sample profile</span>
        <p className="sample-note">Generated demo data. The demo user is signed in by default.</p>
      </div>
      <p id={`${id}-intro`} className="pf-intro">
        People, For you and My brief rank against this profile. Saving updates them right away.
      </p>

      {errors.form && (
        <p className="pf-alert" role="alert">
          {errors.form}
        </p>
      )}
      {errorCount > 0 && !errors.form && (
        <p className="pf-alert" role="alert">
          {errorCount === 1 ? 'One field needs attention.' : `${errorCount} fields need attention.`}
        </p>
      )}

      <Section icon={<UserRound size={15} aria-hidden="true" />} title="Basics">
        {text('name', 'Name', { required: true, autoComplete: 'name' })}
        <div className="pf-two">
          {text('title', 'Role', { autoComplete: 'organization-title' })}
          {text('company', 'Company', { list: options.companies, autoComplete: 'organization' })}
        </div>
        <div className="pf-two">
          {text('city', 'City', { list: options.cities })}
          {text('country', 'Country', { list: options.countries })}
        </div>
        <Field id={`${id}-bio`} label="Bio" error={errors.bio} count={`${draft.bio.length} / ${LIMITS.bio}`}>
          {(props) => (
            <textarea
              {...props}
              className="pf-input pf-textarea"
              rows={3}
              maxLength={LIMITS.bio}
              value={draft.bio}
              onChange={(e) => set('bio', e.target.value)}
            />
          )}
        </Field>
      </Section>

      <Section icon={<Sparkles size={15} aria-hidden="true" />} title="Interests and keywords">
        <ChipInput
          label="Interests"
          hint="Short topics, like eBPF or GPU scheduling."
          values={draft.interests}
          onChange={(v) => set('interests', v)}
          suggestions={options.interests}
          max={LIMITS.interests}
          maxLength={LIMITS.phrase}
          placeholder="Add an interest"
          error={errors.interests}
        />
        <ChipInput
          label="Keywords and projects"
          hint="CNCF projects or tools you use."
          values={draft.projects}
          onChange={(v) => set('projects', v)}
          suggestions={options.projects}
          max={LIMITS.projects}
          maxLength={LIMITS.phrase}
          placeholder="Add a project"
          error={errors.projects}
        />
      </Section>

      <Section icon={<GraduationCap size={15} aria-hidden="true" />} title="Background" note="Finds alumni, former colleagues and your communities.">
        <ChipInput
          label="Schools"
          values={draft.schools}
          onChange={(v) => set('schools', v)}
          suggestions={options.schools}
          max={8}
          maxLength={LIMITS.short}
          placeholder="Add a university"
          error={errors.schools}
        />
        <ChipInput
          label="Past companies"
          values={draft.past_companies}
          onChange={(v) => set('past_companies', v)}
          suggestions={options.companies}
          max={10}
          maxLength={LIMITS.short}
          placeholder="Add a company"
          error={errors.past_companies}
        />
        <ChipInput
          label="Communities"
          values={draft.communities}
          onChange={(v) => set('communities', v)}
          suggestions={options.communities}
          max={10}
          maxLength={LIMITS.short}
          placeholder="Add a community"
          error={errors.communities}
        />
      </Section>

      <fieldset className="pf-section" aria-describedby={`${id}-tracks-hint`}>
        <legend className="pf-legend">
          <Target size={15} aria-hidden="true" /> Tracks
        </legend>
        <p id={`${id}-tracks-hint`} className="pf-hint">
          Sessions in these tracks count as for you. {draft.tracks.length} chosen{tracksFull ? `, the most allowed` : ''}.
        </p>
        {options.tracks.length === 0 && draft.tracks.length === 0 && <p className="pf-hint">Loading tracks&hellip;</p>}
        <div className="pf-tracks">
          {[...new Set([...draft.tracks, ...options.tracks])].map((t) => (
            <label key={t} className="pf-track">
              <input
                type="checkbox"
                checked={trackSet.has(t)}
                disabled={!trackSet.has(t) && tracksFull}
                onChange={(e) => set('tracks', e.target.checked ? [...draft.tracks, t] : draft.tracks.filter((x) => x !== t))}
              />
              <span>{t}</span>
            </label>
          ))}
        </div>
        {errors.tracks && <p className="pf-error">{errors.tracks}</p>}
      </fieldset>

      <Section icon={<Briefcase size={15} aria-hidden="true" />} title="Looking for">
        <Field id={`${id}-looking`} label="Who do you want to meet this week?" error={errors.looking_for} count={`${draft.looking_for.length} / ${LIMITS.lookingFor}`}>
          {(props) => (
            <textarea
              {...props}
              className="pf-input pf-textarea"
              rows={2}
              maxLength={LIMITS.lookingFor}
              value={draft.looking_for}
              placeholder="For example: people running inference on shared GPU clusters"
              onChange={(e) => set('looking_for', e.target.value)}
            />
          )}
        </Field>
      </Section>

      <Section icon={<Link2 size={15} aria-hidden="true" />} title="Links" note={`Up to ${LIMITS.links}, shown on your card.`}>
        {draft.links.map((link, i) => (
          <Field
            key={i}
            id={`${id}-link-${i}`}
            label={`Link ${i + 1}`}
            error={errors.links && link.trim() && !isUrl(link.trim()) ? 'Not a full web address. Start with https://' : undefined}
          >
            {(props) => (
              <input
                {...props}
                className="pf-input"
                type="url"
                inputMode="url"
                autoComplete="url"
                value={link}
                placeholder={['https://github.com/you', 'https://linkedin.com/in/you', 'https://your.site'][i]}
                onChange={(e) => set('links', draft.links.map((l, j) => (j === i ? e.target.value : l)))}
              />
            )}
          </Field>
        ))}
        {errors.links && draft.links.every((l) => !l.trim() || isUrl(l.trim())) && <p className="pf-error">{errors.links}</p>}
      </Section>

      <fieldset className="pf-section">
        <legend className="pf-legend">
          <Eye size={15} aria-hidden="true" /> Visibility
        </legend>
        <label className="pf-radio">
          <input type="radio" name={`${id}-visibility`} checked={draft.visibility === 'public'} onChange={() => set('visibility', 'public')} />
          <span>
            Public <span className="pf-hint">Others can find you in People and ask to meet.</span>
          </span>
        </label>
        <label className="pf-radio">
          <input type="radio" name={`${id}-visibility`} checked={draft.visibility === 'private'} onChange={() => set('visibility', 'private')} />
          <span>
            Private <span className="pf-hint">Hidden from other people&apos;s matches; your own ranking still uses it.</span>
          </span>
        </label>
      </fieldset>

      <div className="pf-actions">
        <p className="pf-dirty" aria-live="polite">{dirty ? 'Unsaved changes' : 'No changes'}</p>
        <button type="button" className="pf-secondary" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="btn-primary" disabled={!dirty || saving} aria-disabled={!dirty || saving}>
          {saving ? <LoaderCircle size={16} className="pf-spin" aria-hidden="true" /> : <Save size={16} aria-hidden="true" />}
          {saving ? 'Saving…' : 'Save profile'}
        </button>
      </div>
    </form>
  )
}

function Section({ icon, title, note, children }: { icon: ReactNode; title: string; note?: string; children: ReactNode }) {
  return (
    <fieldset className="pf-section">
      <legend className="pf-legend">
        {icon} {title}
      </legend>
      {note && <p className="pf-hint">{note}</p>}
      {children}
    </fieldset>
  )
}

type ControlProps = { id: string; 'aria-invalid'?: boolean; 'aria-describedby'?: string }

function Field({
  id,
  label,
  error,
  count,
  required,
  children,
}: {
  id: string
  label: string
  error?: string
  count?: string
  required?: boolean
  children: (props: ControlProps) => ReactNode
}) {
  const described = [count ? `${id}-count` : '', error ? `${id}-error` : ''].filter(Boolean).join(' ')
  return (
    <div className="pf-field">
      <label htmlFor={id} className="pf-label">
        {label}
        {required && <span className="pf-required"> (required)</span>}
      </label>
      {children({ id, 'aria-invalid': error ? true : undefined, 'aria-describedby': described || undefined })}
      {count && (
        <p id={`${id}-count`} className="pf-hint pf-count">
          {count}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="pf-error">
          {error}
        </p>
      )}
    </div>
  )
}
