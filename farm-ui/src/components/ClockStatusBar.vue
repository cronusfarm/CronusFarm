<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { apiJson } from '@/api/cronusfarm'
import { useDevice } from '@/composables/useDevice'

const props = defineProps({
  pollMs: { type: Number, default: 5000 },
})

const { deviceId } = useDevice()
const browserNow = ref('')
const piNow = ref('—')
const controlNow = ref('—')
const arduinoNow = ref('—')
const skewSec = ref(null)
const piTz = ref('')
const err = ref('')
const syncing = ref(false)

let tickTimer = null
let pollTimer = null

function fmtLocal(ms) {
  if (ms == null || !Number.isFinite(ms)) return '—'
  return new Date(ms).toLocaleString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

function fmtRtc14(s) {
  if (!s || s.length < 14) return '—'
  const y = s.slice(0, 4)
  const mo = s.slice(4, 6)
  const d = s.slice(6, 8)
  const h = s.slice(8, 10)
  const mi = s.slice(10, 12)
  const sec = s.slice(12, 14)
  return `${y}-${mo}-${d} ${h}:${mi}:${sec}`
}

function tickBrowser() {
  browserNow.value = fmtLocal(Date.now())
}

async function loadTimes() {
  try {
    const j = await apiJson(
      `/api/time/status?device_id=${encodeURIComponent(deviceId.value)}`,
    )
    piNow.value = j.pi_local_display || fmtLocal(j.pi_ts_ms)
    piTz.value = j.pi_tz || ''
    controlNow.value = j.control_display || fmtLocal(j.last_tele_ts_ms)
    arduinoNow.value = j.arduino_rtc_display || fmtRtc14(j.arduino_rtc_local)
    skewSec.value =
      j.arduino_skew_sec != null && Number.isFinite(j.arduino_skew_sec)
        ? j.arduino_skew_sec
        : null
    err.value = ''
  } catch (e) {
    err.value = e.message || String(e)
  }
}

async function syncRtc() {
  syncing.value = true
  err.value = ''
  try {
    const j = await apiJson('/api/rtc/sync_to_device', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      body: JSON.stringify({ device_id: deviceId.value }),
    })
    if (j.error) throw new Error(j.error)
    await loadTimes()
  } catch (e) {
    err.value = e.message || String(e)
  } finally {
    syncing.value = false
  }
}

onMounted(() => {
  tickBrowser()
  tickTimer = setInterval(tickBrowser, 1000)
  loadTimes()
  pollTimer = setInterval(loadTimes, props.pollMs)
})

onUnmounted(() => {
  if (tickTimer) clearInterval(tickTimer)
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div class="cf-clock-bar">
    <div class="cf-clock-grid">
      <div class="cf-clock-item">
        <span class="cf-clock-lab">브라우저(PC)</span>
        <span class="cf-clock-val">{{ browserNow }}</span>
      </div>
      <div class="cf-clock-item">
        <span class="cf-clock-lab">Pi 시스템</span>
        <span class="cf-clock-val">{{ piNow }}</span>
        <span v-if="piTz" class="cf-clock-sub">{{ piTz }}</span>
      </div>
      <div class="cf-clock-item">
        <span class="cf-clock-lab">제어(tele 수신)</span>
        <span class="cf-clock-val">{{ controlNow }}</span>
      </div>
      <div class="cf-clock-item">
        <span class="cf-clock-lab">Arduino RTC</span>
        <span class="cf-clock-val">{{ arduinoNow }}</span>
        <span v-if="skewSec != null" class="cf-clock-sub" :class="{ warn: Math.abs(skewSec) > 30 }">
          Pi 대비 {{ skewSec > 0 ? '+' : '' }}{{ skewSec }}초
        </span>
      </div>
    </div>
    <div class="cf-clock-actions">
      <button type="button" class="btn btn-sm" :disabled="syncing" @click="loadTimes">새로고침</button>
      <button type="button" class="btn btn-sm btn-prim" :disabled="syncing" @click="syncRtc">
        Pi 시각 → Arduino RTC
      </button>
    </div>
    <p v-if="err" class="cf-clock-err">{{ err }}</p>
    <p v-else class="cf-clock-hint">
      패널 LCD는 Arduino RTC(24시간)를 표시합니다. 어긋나면 「Pi 시각 → Arduino RTC」로 맞추세요.
    </p>
  </div>
</template>
