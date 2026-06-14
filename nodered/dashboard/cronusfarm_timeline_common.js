/**
 * 모니터 Bed 타임라인 — farm-ui Sch24hChart 와 동일 tele ON 구간 렌더
 * (Node-RED ui_template / 정적 httpStatic)
 */
(function (g) {
  'use strict'

  function mergeTeleLiveTail(execData, tEnd, nowMs) {
    const points = execData?.points ? execData.points.slice() : []
    const live = execData?.live_at_now
    if (!live || live.state == null) return points
    const st = Number(live.state) === 1 ? 1 : 0
    const ts = Math.min(nowMs, tEnd)
    const last = points.length ? points[points.length - 1] : null
    if (last && Number(last.ts_ms) === ts && Number(last.state) === st) return points
    if (last && Number(last.ts_ms) === ts) {
      points[points.length - 1] = Object.assign({}, last, {
        state: st,
        auto_mode: live.auto_mode,
      })
      return points
    }
    points.push({ ts_ms: ts, state: st, auto_mode: live.auto_mode })
    return points
  }

  /** tele ON 구간만 (설정 노란과 동일) */
  function teleOnSegments(points, tStart, tEnd, nowMs) {
    const clipEnd = Math.min(nowMs, tEnd)
    if (!points?.length) return []
    const sorted = points
      .map(function (p) {
        return { ts_ms: Number(p.ts_ms), state: Number(p.state) === 1 ? 1 : 0 }
      })
      .filter(function (p) {
        return Number.isFinite(p.ts_ms) && p.ts_ms <= clipEnd
      })
      .sort(function (a, b) {
        return a.ts_ms - b.ts_ms
      })
    if (!sorted.length) return []

    if (sorted.length === 1) {
      if (sorted[0].state !== 1) return []
      const t0 = Math.max(tStart, sorted[0].ts_ms)
      if (clipEnd > t0) return [{ t0: t0, t1: clipEnd }]
      return []
    }

    const segs = []
    for (let i = 0; i < sorted.length - 1; i++) {
      if (sorted[i].state !== 1) continue
      const t0 = Math.max(tStart, sorted[i].ts_ms)
      const t1 = Math.min(sorted[i + 1].ts_ms, clipEnd)
      if (t1 <= t0 || t0 >= clipEnd) continue
      segs.push({ t0: t0, t1: t1 })
    }
    const last = sorted[sorted.length - 1]
    if (last.state === 1 && last.ts_ms < clipEnd) {
      const t0 = Math.max(tStart, last.ts_ms)
      if (clipEnd > t0) segs.push({ t0: t0, t1: clipEnd })
    }
    return segs
  }

  /** 모니터: 지금−24h ~ 지금 */
  function mapRolling24h(j) {
    const tEnd =
      j?.window_end_ms != null && Number.isFinite(Number(j.window_end_ms))
        ? Number(j.window_end_ms)
        : Date.now()
    const tStart = tEnd - 24 * 3600 * 1000
    return { tStart: tStart, tEnd: tEnd, nowMs: tEnd }
  }

  function drawMsSegments(ctx, xs, area, segments, fillStyle, strokeStyle) {
    if (!segments?.length || !xs || !area) return
    const top = area.top + 1
    const h = Math.max(1, area.bottom - area.top - 2)
    for (const seg of segments) {
      const x1 = xs.getPixelForValue(seg.t0)
      const x2 = xs.getPixelForValue(seg.t1)
      if (!Number.isFinite(x1) || !Number.isFinite(x2)) continue
      const left = Math.min(x1, x2)
      const w = Math.max(1, Math.abs(x2 - x1))
      ctx.fillStyle = fillStyle
      ctx.fillRect(left, top, w, h)
      if (strokeStyle) {
        ctx.strokeStyle = strokeStyle
        ctx.lineWidth = 1
        ctx.strokeRect(left, top, w, h)
      }
    }
  }

  g.CfTimeline = {
    mergeTeleLiveTail: mergeTeleLiveTail,
    teleOnSegments: teleOnSegments,
    mapRolling24h: mapRolling24h,
    drawMsSegments: drawMsSegments,
    TELE_FILL: 'rgba(255,214,10,0.08)',
    TELE_STROKE: 'rgba(255,214,10,0.28)',
  }
})(typeof window !== 'undefined' ? window : globalThis)
