import { ref } from 'vue'
import { apiJson } from '@/api/cronusfarm'

/** 전 채널 schedule_rule — 모듈 단일 캐시(설정·Beds·24h 차트 공유) */
const rulesByChannel = ref({})
let inflight = null
let lastDeviceId = ''

export function useScheduleBatch() {
  async function loadSchedules(deviceId, { force = false } = {}) {
    const id = (deviceId || '').trim() || 'cronusfarm-01'
    if (!force && inflight && lastDeviceId === id) {
      await inflight
      return rulesByChannel.value
    }
    if (!force && lastDeviceId === id && Object.keys(rulesByChannel.value).length) {
      return rulesByChannel.value
    }
    lastDeviceId = id
    inflight = (async () => {
      try {
        const j = await apiJson(
          `/api/schedule/batch?device_id=${encodeURIComponent(id)}`,
        )
        const next = {}
        const ch = j.channels || {}
        for (const [key, val] of Object.entries(ch)) {
          next[key] = val?.rules || []
        }
        rulesByChannel.value = next
      } catch (e) {
        console.warn('schedule batch', e)
        rulesByChannel.value = {}
      } finally {
        inflight = null
      }
      return rulesByChannel.value
    })()
    return inflight
  }

  function rulesFor(channel) {
    return rulesByChannel.value[channel] || []
  }

  function invalidate() {
    rulesByChannel.value = {}
    lastDeviceId = ''
    inflight = null
  }

  return { rulesByChannel, loadSchedules, rulesFor, invalidate }
}
