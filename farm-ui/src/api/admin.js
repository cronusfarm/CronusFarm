const BASE = '/farm/cronusfarm-sqlite'

async function req(method, path, body) {
  const opt = { method, credentials: 'include', headers: {} }
  if (body != null) {
    opt.headers['Content-Type'] = 'application/json'
    opt.body = JSON.stringify(body)
  }
  const r = await fetch(`${BASE}${path}`, opt)
  const data = await r.json().catch(() => ({}))
  if (!r.ok) {
    const err = new Error(data.error || data || r.statusText)
    err.status = r.status
    err.data = data
    throw err
  }
  return data
}

export const adminApi = {
  me: () => req('GET', '/api/admin/me'),
  authVerify: () => req('GET', '/api/auth/verify'),
  members: () => req('GET', '/api/admin/members'),
  saveMember: (body) => req('POST', '/api/admin/members', body),
  updateMember: (body) => req('PUT', '/api/admin/members', body),
  telegramUsers: (status = '') => {
    const q = status ? `?status=${encodeURIComponent(status)}` : ''
    return req('GET', `/api/admin/telegram-users${q}`)
  },
  saveTelegramUser: (body) => req('POST', '/api/admin/telegram-users', body),
  updateTelegramUser: (body) => req('PUT', '/api/admin/telegram-users', body),
  deleteTelegramUser: (id) => req('DELETE', `/api/admin/telegram-users?id=${id}`),
  notifyPrefs: () => req('GET', '/api/admin/notify-prefs'),
  saveNotifyPref: (body) => req('POST', '/api/admin/notify-prefs', body),
  updateNotifyPref: (body) => req('PUT', '/api/admin/notify-prefs', body),
  news: (q = '') => req('GET', `/api/admin/news?q=${encodeURIComponent(q)}`),
  farmDiary: () => req('GET', '/api/admin/farm-diary'),
  saveDiary: (body) => req('POST', '/api/admin/farm-diary', body),
  deleteDiary: (id) => req('DELETE', `/api/admin/farm-diary?id=${id}`),
  pestForecast: () => req('GET', '/api/admin/pest-forecast'),
  aiDiagnose: (body) => req('POST', '/api/admin/ai-diagnose', body),
  authStatus: (siteHost = '') => {
    const q = siteHost ? `?site_host=${encodeURIComponent(siteHost)}` : ''
    return req('GET', `/api/admin/auth-status${q}`)
  },
  reset: (target) => req('POST', `/api/admin/reset/${target}`, {}),
}
