import { ref } from 'vue'
import { apiJson } from '@/api/cronusfarm'
import { useDevice } from '@/composables/useDevice'

/** Pi(KST) ↔ 브라우저 skew(ms). 운영 「지금」·24h 달력 창 단일 소스 */
const serverOffsetMs = ref(0)
const dayAnchorMs = ref(null)
const dayEndMs = ref(null)
const piLocalDisplay = ref('')
const piTz = ref('Asia/Seoul')

let pollTimer = null

export function usePiClock() {
  const { deviceId } = useDevice()

  async function syncPiClock() {
    try {
      const j = await apiJson('/api/time/now')
      const pi = Number(j.pi_ts_ms)
      if (Number.isFinite(pi)) {
        serverOffsetMs.value = pi - Date.now()
      }
      if (j.pi_local_display) piLocalDisplay.value = String(j.pi_local_display)
      if (j.pi_tz) piTz.value = String(j.pi_tz)
      const a = Number(j.day_anchor_ms)
      const e = Number(j.day_end_ms)
      if (Number.isFinite(a) && Number.isFinite(e) && e > a) {
        dayAnchorMs.value = a
        dayEndMs.value = e
      }
    } catch {
      /* ignore */
    }
  }

  /** 그래프·스케줄 판정용 「지금」(Pi 시계) */
  function piNowMs() {
    return Date.now() + serverOffsetMs.value
  }

  function piDayWindow() {
    if (dayAnchorMs.value != null && dayEndMs.value != null) {
      return {
        anchor_ts_ms: dayAnchorMs.value,
        day_end_ms: dayEndMs.value,
      }
    }
    return null
  }

  return {
    serverOffsetMs,
    dayAnchorMs,
    dayEndMs,
    piLocalDisplay,
    piTz,
    syncPiClock,
    piNowMs,
    piDayWindow,
    /** @deprecated piNowMs */
    chartNowMs: piNowMs,
    /** @deprecated syncPiClock */
    syncServerClock: syncPiClock,
  }
}

export function ensurePiClockPolling() {
  const { syncPiClock } = usePiClock()
  if (pollTimer) return
  syncPiClock()
  pollTimer = setInterval(() => syncPiClock(), 15000)
}

export function stopPiClockPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

/** 하위 호환 */
export const useChartClock = usePiClock
export const ensureChartClockPolling = ensurePiClockPolling
export const stopChartClockPolling = stopPiClockPolling
