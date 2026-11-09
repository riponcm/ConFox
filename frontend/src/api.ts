/**
 * The one way pages call the API. Same-origin /api calls carry the trace header added by the Dash0 SDK,
 * so every browser request joins its backend trace.
 */
export const DEMO_USER = 'emma'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
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
