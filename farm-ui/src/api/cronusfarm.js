/** CronusFarm SQLite 브리지 — nginx /farm/cronusfarm-sqlite 프록시 */
export const API_BASE = '/farm/cronusfarm-sqlite'

export function apiUrl(path) {
  const p = path.startsWith('/') ? path : `/${path}`
  return `${typeof location !== 'undefined' ? location.origin : ''}${API_BASE}${p}`
}

const DEFAULT_TIMEOUT_MS = 8000

export async function apiFetch(path, options = {}) {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, signal: outerSignal, ...rest } = options
  const controller = new AbortController()
  const timer =
    timeoutMs > 0
      ? setTimeout(() => controller.abort(new Error('요청 시간 초과')), timeoutMs)
      : null
  if (outerSignal) {
    outerSignal.addEventListener('abort', () => controller.abort(outerSignal.reason), {
      once: true,
    })
  }
  try {
    const r = await fetch(apiUrl(path), {
      credentials: 'same-origin',
      signal: controller.signal,
      ...rest,
    })
    return r
  } finally {
    if (timer) clearTimeout(timer)
  }
}

export async function apiJson(path, options = {}) {
  const r = await apiFetch(path, options)
  const j = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(j.error || `HTTP ${r.status}`)
  return j
}
