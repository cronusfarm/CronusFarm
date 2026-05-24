/** 스케줄 판정·오늘 0~24h 창 — Sch24hChart 단일 캔버스 겹침(계획+실제) */

const DOW_BITS = [64, 1, 2, 4, 8, 16, 32] // 일~토

const CF_TZ = 'Asia/Seoul'

/** 오늘 0:00 ~ 내일 0:00 (Asia/Seoul — Pi·Arduino 운영 타임존) */
export function calendarDayWindow(refMs = Date.now()) {
  const ymd = new Intl.DateTimeFormat('en-CA', {
    timeZone: CF_TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date(refMs))
  const tStart = Date.parse(`${ymd}T00:00:00+09:00`)
  const tEnd = tStart + 24 * 3600 * 1000
  return { tStart, tEnd, nowMs: refMs }
}

/** anchor가 KST 0:00~0:05 근처인지 (UTC 자정 등 잘못된 anchor 거부) */
export function isKstMidnightAnchor(tsMs) {
  if (!Number.isFinite(tsMs)) return false
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: CF_TZ,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(new Date(tsMs))
  const h = parseInt(parts.find((p) => p.type === 'hour')?.value || '99', 10)
  const m = parseInt(parts.find((p) => p.type === 'minute')?.value || '99', 10)
  return h === 0 && m < 5
}

/**
 * 24h 그래프 공통 창 — KST 오늘 0:00~24:00, now는 호출부(Pi 동기 시계).
 * window_end_ms(조회 시각)는 x축 끝·빨간 선에 절대 사용하지 않음.
 */
export function cfDayWindowMs(execData, dayWindow, nowMs = Date.now()) {
  const dw = dayWindow || execData?.day_window
  if (dw?.anchor_ts_ms != null && Number.isFinite(Number(dw.anchor_ts_ms))) {
    const tStart = Number(dw.anchor_ts_ms)
    const tEnd = Number.isFinite(Number(dw.day_end_ms))
      ? Number(dw.day_end_ms)
      : tStart + 24 * 3600 * 1000
    if (tEnd > tStart) return { tStart, tEnd, nowMs }
  }

  let tStart =
    execData?.anchor_ts_ms != null && Number.isFinite(Number(execData.anchor_ts_ms))
      ? Number(execData.anchor_ts_ms)
      : null

  if (tStart != null && !isKstMidnightAnchor(tStart)) {
    tStart = null
  }

  if (tStart == null) {
    const w = calendarDayWindow(nowMs)
    return { tStart: w.tStart, tEnd: w.tEnd, nowMs }
  }

  const span =
    execData?.window_day_end_ms != null &&
    Number.isFinite(Number(execData.window_day_end_ms))
      ? Number(execData.window_day_end_ms) - tStart
      : 24 * 3600 * 1000
  const dayMs = 24 * 3600 * 1000
  const tEnd =
    span >= dayMs * 0.9 && span <= dayMs * 1.1
      ? tStart + span
      : tStart + dayMs
  return { tStart, tEnd, nowMs }
}

/** @deprecated cfDayWindowMs 사용 */
export function mapTimelineWindow(execData, dayWindow, nowMs) {
  const { tStart, tEnd } = cfDayWindowMs(execData, dayWindow, nowMs)
  return { tStart, tEnd }
}

/** API live_at_now + points → tele 끝점을 지금 시각까지 보간 */
export function mergeTeleLiveTail(execData, tEnd, nowMs) {
  const points = execData?.points ? [...execData.points] : []
  const live = execData?.live_at_now
  if (!live || live.state == null) return points
  const st = Number(live.state) === 1 ? 1 : 0
  const ts = Math.min(nowMs, tEnd)
  const last = points.length ? points[points.length - 1] : null
  if (last && Number(last.ts_ms) === ts && Number(last.state) === st) return points
  if (last && Number(last.ts_ms) === ts) {
    points[points.length - 1] = { ...last, state: st, auto_mode: live.auto_mode }
    return points
  }
  points.push({ ts_ms: ts, state: st, auto_mode: live.auto_mode })
  return points
}

function dowMaskForTs(tsMs) {
  // 브라우저 로컬 타임존이 달라도 KST 기준으로 요일이 고정되어야 함
  const w = new Intl.DateTimeFormat('en-US', { timeZone: CF_TZ, weekday: 'short' }).format(
    new Date(tsMs),
  )
  // en-US: Sun/Mon/Tue/Wed/Thu/Fri/Sat
  const idx =
    w === 'Sun'
      ? 0
      : w === 'Mon'
        ? 1
        : w === 'Tue'
          ? 2
          : w === 'Wed'
            ? 3
            : w === 'Thu'
              ? 4
              : w === 'Fri'
                ? 5
                : 6
  return DOW_BITS[idx]
}

function minutesOfDay(tsMs) {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: CF_TZ,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(new Date(tsMs))
  const h = parseInt(parts.find((p) => p.type === 'hour')?.value || '0', 10) || 0
  const m = parseInt(parts.find((p) => p.type === 'minute')?.value || '0', 10) || 0
  return h * 60 + m
}

function secondsOfDay(tsMs) {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: CF_TZ,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(new Date(tsMs))
  const h = parseInt(parts.find((p) => p.type === 'hour')?.value || '0', 10) || 0
  const m = parseInt(parts.find((p) => p.type === 'minute')?.value || '0', 10) || 0
  const s = parseInt(parts.find((p) => p.type === 'second')?.value || '0', 10) || 0
  return h * 3600 + m * 60 + s
}

/** 해당 시각에 스케줄 규칙상 ON 여부 */
export function isScheduleOnAt(rules, tsMs) {
  const list = rules || []
  const dow = dowMaskForTs(tsMs)
  const mod = minutesOfDay(tsMs)
  const secDay = secondsOfDay(tsMs)

  for (const r of list) {
    if (r.enabled === 0 || r.enabled === false) continue
    const kind = r.rule_kind || 'window'
    const mask = parseInt(r.dow_mask, 10) || 0
    if (!(mask & dow)) continue

    if (kind === 'cycle') {
      const onMin = parseInt(r.on_min, 10) || 0
      const offMin = parseInt(r.off_min, 10) || 0
      if (onMin !== 0 || offMin !== 0) {
        if (offMin > onMin) {
          if (!(mod >= onMin && mod < offMin)) continue
        } else if (offMin < onMin) {
          if (!(mod >= onMin || mod < offMin)) continue
        } else {
          continue
        }
      }
      const onSec = parseInt(r.on_sec, 10) || 0
      const offSec = parseInt(r.off_sec, 10) || 0
      const period = onSec + offSec
      if (!period) continue
      const phase = secDay % period
      if (phase < onSec) return true
      continue
    }

    const on = parseInt(r.on_min, 10) || 0
    const off = parseInt(r.off_min, 10) || 0
    if (off > on) {
      if (mod >= on && mod < off) return true
    } else if (off < on) {
      if (mod >= on || mod < off) return true
    } else if (mod === on) {
      return true
    }
  }
  return false
}

/** tele → 오늘 창 클립·보간 (Chart.js stepped용) */
export function normalizeTeleForDay(points, tStart, tEnd, nowMs) {
  if (!points?.length) return []
  const sorted = [...points]
    .map((p) => ({
      ts_ms: Number(p.ts_ms),
      state: Number(p.state),
      auto_mode: p.auto_mode,
    }))
    .filter((p) => Number.isFinite(p.ts_ms))
    .sort((a, b) => a.ts_ms - b.ts_ms)

  const clipEnd = Math.min(nowMs, tEnd)
  // 미래 시각(타임존 오해·잘못된 ts_ms)은 그래프에 넣지 않음
  const inWin = sorted.filter((p) => p.ts_ms >= tStart && p.ts_ms <= clipEnd)
  let out = inWin

  const before = sorted.filter((p) => p.ts_ms < tStart)
  if (before.length) {
    const last = before[before.length - 1]
    out = [{ ts_ms: tStart, state: last.state, auto_mode: last.auto_mode }, ...out]
  } else if (out.length && out[0].ts_ms > tStart) {
    out = [{ ts_ms: tStart, state: out[0].state, auto_mode: out[0].auto_mode }, ...out]
  }

  const inClip = sorted.filter((p) => p.ts_ms <= clipEnd)
  const latest = inClip.length ? inClip[inClip.length - 1] : null
  const endState =
    latest && latest.ts_ms <= nowMs
      ? latest.state
      : out.length
        ? out[out.length - 1].state
        : 0
  const endTs = clipEnd
  if (!out.length || out[out.length - 1].ts_ms < endTs) {
    out = [...out, { ts_ms: endTs, state: endState, auto_mode: latest?.auto_mode }]
  }
  return out
}

function minCyclePeriodMs(rules) {
  let minP = 24 * 3600 * 1000
  for (const r of rules || []) {
    if ((r.rule_kind || 'window') !== 'cycle') continue
    const onSec = parseInt(r.on_sec, 10) || 0
    const offSec = parseInt(r.off_sec, 10) || 0
    const p = (onSec + offSec) * 1000
    if (p > 0 && p < minP) minP = p
  }
  return minP
}

/** 스케줄 규칙 → Chart.js {x,y} stepped 데이터 */
export function scheduleToStepData(rules, tStart, tEnd) {
  const span = tEnd - tStart
  const minPeriod = minCyclePeriodMs(rules)
  const step = Math.max(
    15 * 1000,
    Math.min(Math.floor(minPeriod / 4) || span, Math.floor(span / 360)),
  )
  const data = []
  let lastY = isScheduleOnAt(rules, tStart) ? 1 : 0
  data.push({ x: tStart, y: lastY })

  for (let t = tStart + step; t < tEnd; t += step) {
    const y = isScheduleOnAt(rules, t) ? 1 : 0
    if (y !== lastY) {
      data.push({ x: t, y: lastY })
      data.push({ x: t, y })
      lastY = y
    }
  }
  const endY = isScheduleOnAt(rules, tEnd - 1) ? 1 : 0
  if (data[data.length - 1].y !== endY) {
    data.push({ x: tEnd, y: lastY })
    if (lastY !== endY) data.push({ x: tEnd, y: endY })
  } else {
    data.push({ x: tEnd, y: endY })
  }
  return data
}

/** 스케줄 ON 구간(ms) — 오늘 0~24h 전체(canvas 막대) */
export function scheduleOnSegments(rules, tStart, tEnd) {
  return stepDataOnSegments(scheduleToStepData(rules, tStart, tEnd), tEnd)
}

/**
 * tele ON 구간 — API fact 점만 사용(보간·live tail·자정 보간 없음).
 * 인접 두 점 사이 state===1 일 때만 [p0.ts, p1.ts) 막대, nowMs 초과 분은 그리지 않음.
 */
export function teleOnSegments(points, tStart, tEnd, nowMs) {
  const clipEnd = Math.min(nowMs, tEnd)
  if (!points?.length) return []
  const sorted = [...points]
    .map((p) => ({
      ts_ms: Number(p.ts_ms),
      state: Number(p.state) === 1 ? 1 : 0,
    }))
    .filter((p) => Number.isFinite(p.ts_ms) && p.ts_ms <= clipEnd)
    .sort((a, b) => a.ts_ms - b.ts_ms)
  if (!sorted.length) return []

  if (sorted.length === 1) {
    if (sorted[0].state !== 1) return []
    const t0 = Math.max(tStart, sorted[0].ts_ms)
    if (clipEnd > t0) return [{ t0, t1: clipEnd }]
    return []
  }

  const segs = []
  for (let i = 0; i < sorted.length - 1; i++) {
    if (sorted[i].state !== 1) continue
    const t0 = Math.max(tStart, sorted[i].ts_ms)
    const t1 = Math.min(sorted[i + 1].ts_ms, clipEnd)
    if (t1 <= t0 || t0 >= clipEnd) continue
    segs.push({ t0, t1 })
  }
  const last = sorted[sorted.length - 1]
  if (last.state === 1 && last.ts_ms < clipEnd) {
    const t0 = Math.max(tStart, last.ts_ms)
    if (clipEnd > t0) segs.push({ t0, t1: clipEnd })
  }
  return segs
}

/** 빨간 선용 now(ms) — tEnd는 내일 0시이므로 window_end_ms로 잘리지 않음 */
export function nowMarkerMs(tStart, tEnd, nowMs) {
  if (!Number.isFinite(tStart) || !Number.isFinite(tEnd) || tEnd <= tStart) return null
  if (!Number.isFinite(nowMs)) return null
  if (nowMs >= tEnd) return tEnd - 1
  if (nowMs <= tStart) return tStart
  return nowMs
}

/** 빨간 현재 시각선 표시 가능(자정 직전·직후 제외) */
export function shouldShowNowMarker(tStart, tEnd, nowMs) {
  const now = nowMarkerMs(tStart, tEnd, nowMs)
  if (now == null) return false
  return now > tStart + 60_000 && now < tEnd - 60_000
}

/** timeline API 응답이 그릴 수 있는지 */
export function hasTeleTimelineData(execData) {
  if (execData == null) return false
  if (execData.live_at_now != null && execData.live_at_now.state != null) return true
  return Array.isArray(execData.points) && execData.points.length >= 1
}

/** stepped {x,y} 에서 y=1 구간 → canvas 막대용 */
export function stepDataOnSegments(data, clipEnd) {
  if (!data?.length || !Number.isFinite(clipEnd)) return []
  const segs = []
  let onStart = null
  for (const p of data) {
    if (p.x > clipEnd) break
    const on = p.y === 1
    if (on && onStart == null) onStart = p.x
    if (!on && onStart != null) {
      segs.push({ t0: onStart, t1: p.x })
      onStart = null
    }
  }
  if (onStart != null) {
    const t1 = Math.min(clipEnd, data[data.length - 1].x)
    if (t1 > onStart) segs.push({ t0: onStart, t1 })
  }
  return segs
}

/** tele points → Chart.js stepped */
export function teleToStepData(points, tStart, tEnd, nowMs) {
  const clipEnd = Math.min(nowMs, tEnd)
  const norm = normalizeTeleForDay(points, tStart, tEnd, nowMs).filter(
    (p) => p.ts_ms <= clipEnd,
  )
  if (!norm.length) {
    return [
      { x: tStart, y: 0 },
      { x: clipEnd, y: 0 },
    ]
  }
  const data = []
  let lastY = null
  for (const p of norm) {
    const y = p.state === 1 || p.state === true || Number(p.state) === 1 ? 1 : 0
    const x = p.ts_ms
    if (lastY === null) {
      data.push({ x, y })
      lastY = y
      continue
    }
    if (y !== lastY) {
      data.push({ x, y: lastY })
      data.push({ x, y })
      lastY = y
    }
  }
  if (!data.length) {
    return [
      { x: tStart, y: 0 },
      { x: clipEnd, y: 0 },
    ]
  }
  const last = data[data.length - 1]
  if (last.x < clipEnd) data.push({ x: clipEnd, y: last.y })
  return data
}

/** stepped 데이터를 clipEnd(지금)에서 자름 — Chart.js fill이 x축 끝까지 번지는 것 방지 */
export function clipStepDataAt(data, clipEnd) {
  if (!data?.length || !Number.isFinite(clipEnd)) return data || []
  let y = data[0].y
  const out = []
  for (const p of data) {
    if (p.x > clipEnd) break
    y = p.y
    out.push(p)
  }
  if (!out.length) return [{ x: clipEnd, y: 0 }]
  const last = out[out.length - 1]
  if (last.x < clipEnd) out.push({ x: clipEnd, y })
  return out
}

/** stepped 궤적에서 시각 t의 y (0|1) */
function stepValueAt(data, t) {
  if (!data?.length) return 0
  let y = data[0].y
  for (const p of data) {
    if (p.x > t) break
    y = p.y
  }
  return y === 1 ? 1 : 0
}

/** 계획·실제 모두 ON 구간 → 주황 겹침 (0~24h, 실제는 clipEnd까지) */
export function overlapStepData(schedData, teleData, tStart, clipEnd) {
  const span = clipEnd - tStart
  if (span <= 0) return []
  const step = Math.max(60_000, Math.floor(span / 480))
  const out = []
  let lastY = null
  for (let t = tStart; t <= clipEnd; t += step) {
    const y =
      stepValueAt(schedData, t) === 1 && stepValueAt(teleData, t) === 1 ? 1 : 0
    if (lastY === null) {
      out.push({ x: t, y })
      lastY = y
      continue
    }
    if (y !== lastY) {
      out.push({ x: t, y: lastY })
      out.push({ x: t, y })
      lastY = y
    }
  }
  if (!out.length) {
    return [
      { x: tStart, y: 0 },
      { x: clipEnd, y: 0 },
    ]
  }
  const last = out[out.length - 1]
  if (last.x < clipEnd) out.push({ x: clipEnd, y: last.y })
  return out
}
