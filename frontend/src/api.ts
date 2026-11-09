/**
 * The one way pages call the API. Same-origin /api calls carry the trace header added by the Dash0 SDK,
 * so every browser request joins its backend trace.
 */
export const DEMO_USER = 'emma'

export class ApiError extends Error {
  status: number
  /** The parsed error body, when the API sent JSON (FastAPI puts validation errors in `detail`). */
  detail?: unknown
  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.status = status
    this.detail = detail
  }
}

type Params = Record<string, string | number | boolean | undefined | null | string[]>

export function apiUrl(path: string, params: Params = {}): string {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue
    for (const item of Array.isArray(v) ? v : [v]) q.append(k, String(item))
  }
  const s = q.toString()
  return `/api/${path.replace(/^\//, '')}${s ? `?${s}` : ''}`
}

export async function getJSON<T>(path: string, params?: Params, init?: RequestInit): Promise<T> {
  const r = await fetch(apiUrl(path, params), init)
  if (!r.ok) throw new ApiError(r.status, `${r.status} ${r.statusText}`)
  return (await r.json()) as T
}

export async function postJSON<T>(path: string, body: unknown, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  headers.set('Content-Type', 'application/json')
  const r = await fetch(apiUrl(path), { ...init, method: 'POST', headers, body: JSON.stringify(body) })
  if (!r.ok) throw new ApiError(r.status, `${r.status} ${r.statusText}`)
  return (await r.json()) as T
}

export async function deleteJSON<T>(path: string, params?: Params, init?: RequestInit): Promise<T> {
  const r = await fetch(apiUrl(path, params), { ...init, method: 'DELETE' })
  if (!r.ok) throw new ApiError(r.status, `${r.status} ${r.statusText}`)
  return (await r.json()) as T
}

export async function putJSON<T>(path: string, body: unknown, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  headers.set('Content-Type', 'application/json')
  const r = await fetch(apiUrl(path), { ...init, method: 'PUT', headers, body: JSON.stringify(body) })
  if (!r.ok) {
    const detail = await r.json().then((b: { detail?: unknown }) => b.detail).catch(() => undefined)
    throw new ApiError(r.status, `${r.status} ${r.statusText}`, detail)
  }
  return (await r.json()) as T
}
