/** CronusFarm SQLite 브리지 — nginx /farm/cronusfarm-sqlite 프록시 */
export const API_BASE = '/farm/cronusfarm-sqlite'

export function apiUrl(path) {
  const p = path.startsWith('/') ? path : `/${path}`
  return `${typeof location !== 'undefined' ? location.origin : ''}${API_BASE}${p}`
}

export async function apiFetch(path, options = {}) {
  const r = await fetch(apiUrl(path), {
    credentials: 'same-origin',
    ...options,
  })
  return r
}

export async function apiJson(path, options = {}) {
  const r = await apiFetch(path, options)
  const j = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(j.error || `HTTP ${r.status}`)
  return j
}
