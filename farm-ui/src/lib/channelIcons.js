/** D1 모니터(cf-tile)와 동일 LED / Pump / Fan SVG */

const LED_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4" fill="#FFD54F"/><g stroke="#FFD54F" stroke-width="2" stroke-linecap="round"><path d="M12 2v3"/><path d="M12 19v3"/><path d="M2 12h3"/><path d="M19 12h3"/><path d="M4.2 4.2l2.1 2.1"/><path d="M17.7 17.7l2.1 2.1"/><path d="M19.8 4.2l-2.1 2.1"/><path d="M6.3 17.7l-2.1 2.1"/></g></svg>`

const PUMP_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="#4FC3F7" d="M7 3h10v4h-1v10a4 4 0 0 1-8 0V7H7V3z"/><path fill="#BBDEFB" d="M9 7h6v10a3 3 0 0 1-6 0V7z" opacity=".55"/><path fill="#90CAF9" d="M6 8h2v2H6c-1.1 0-2 .9-2 2v6h2v2H2v-8a4 4 0 0 1 4-4z"/></svg>`

const FAN_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="none" stroke="#2E7D32" stroke-width="2"/><path fill="#43A047" d="M12 7.2c1.6 0 2.3 2.2.9 3.1-.9.6-2.2.3-2.4.9-.2.6.9 1.4.9 2.6 0 1.6-2.2 2.3-3.1.9-.6-.9-.3-2.2-.9-2.4-.6-.2-1.4.9-2.6.9-1.6 0-2.3-2.2-.9-3.1.9-.6 2.2-.3 2.4-.9.2-.6-.9-1.4-.9-2.6 0-1.6 2.2-2.3 3.1-.9.6.9.3 2.4-.9.2-.6-1.4-.9-2.6-.9-1.6 0-2.2-.9-3.1.9-.6 2.2-.3 2.4-.9z"/></svg>`

export function channelIconSvg(kind, size = 26) {
  const n = Number(size) || 26
  let inner = ''
  if (kind === 'led') inner = LED_SVG
  else if (kind === 'pump') inner = PUMP_SVG
  else if (kind === 'fan') inner = FAN_SVG
  else return ''
  return inner.replace('<svg ', `<svg width="${n}" height="${n}" `)
}
