import { ref } from 'vue'
import { apiJson } from '@/api/cronusfarm'
import { useDevice } from '@/composables/useDevice'

/** Pi(KST) ↔ 브라우저 시계 차이(ms). 타임라인·빨간 선에 동일 적용 */
const serverOffsetMs = ref(0)
let pollTimer = null

export function useChartClock() {
  const { deviceId } = useDevice()

  async function syncServerClock() {
    try {
      const j = await apiJson(
        `/api/time/status?device_id=${encodeURIComponent(deviceId.value)}`,
      )
      const pi = Number(j.pi_ts_ms)
      if (Number.isFinite(pi)) {
        serverOffsetMs.value = pi - Date.now()
      }
    } catch {
      /* ignore */
    }
  }

  /** 그래프 「지금」 — Pi 시계 우선(브라우저 오프셋 보정) */
  function chartNowMs() {
    return Date.now() + serverOffsetMs.value
  }

  return { serverOffsetMs, syncServerClock, chartNowMs }
}

export function ensureChartClockPolling() {
  const { syncServerClock } = useChartClock()
  if (pollTimer) return
  syncServerClock()
  pollTimer = setInterval(() => syncServerClock(), 15000)
}

export function stopChartClockPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}
