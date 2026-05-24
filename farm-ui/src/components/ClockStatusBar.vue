<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { apiJson } from '@/api/cronusfarm'
import { useDevice } from '@/composables/useDevice'
import { usePiClock } from '@/composables/usePiClock'

const props = defineProps({
  pollMs: { type: Number, default: 5000 },
})

const { deviceId } = useDevice()
const { piNowMs, piLocalDisplay, syncPiClock } = usePiClock()
const opNow = ref('—')
const piNow = ref('—')
const controlNow = ref('—')
const arduinoNow = ref('—')
const skewSec = ref(null)
const piTz = ref('')
const r4Online = ref(null)
const teleStaleSec = ref(null)
const err = ref('')
const syncMsg = ref('')
const syncing = ref(false)
const refreshing = ref(false)

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

function tickOpNow() {
  opNow.value = piLocalDisplay.value || fmtLocal(piNowMs())
}

async function loadTimes() {
  try {
    await syncPiClock()
    const j = await apiJson(
      `/api/time/status?device_id=${encodeURIComponent(deviceId.value)}`,
    )
    piNow.value = j.pi_local_display || fmtLocal(j.pi_ts_ms)
    tickOpNow()
    piTz.value = j.pi_tz || ''
    controlNow.value = j.control_display || fmtLocal(j.last_tele_ts_ms)
    arduinoNow.value = j.arduino_rtc_display || fmtRtc14(j.arduino_rtc_local)
    skewSec.value =
      j.arduino_skew_sec != null && Number.isFinite(j.arduino_skew_sec)
        ? j.arduino_skew_sec
        : null
    r4Online.value = j.r4_online === true
    teleStaleSec.value =
      j.tele_stale_sec != null && Number.isFinite(j.tele_stale_sec)
        ? j.tele_stale_sec
        : null
    err.value = ''
  } catch (e) {
    err.value = e.message || String(e)
  }
}

async function refreshTimes() {
  refreshing.value = true
  syncMsg.value = ''
  try {
    await loadTimes()
    syncMsg.value = '시각 정보를 새로고침했습니다.'
  } catch (e) {
    err.value = e.message || String(e)
  } finally {
    refreshing.value = false
  }
}

async function syncRtc() {
  syncing.value = true
  err.value = ''
  syncMsg.value = ''
  try {
    const j = await apiJson('/api/rtc/sync_to_device', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      body: JSON.stringify({ device_id: deviceId.value }),
    })
    if (j.error) throw new Error(j.error)
    if (j.warning) {
      syncMsg.value = j.warning
    } else {
      syncMsg.value = `RTC 동기 MQTT 발행 완료 (${j.rtc_local}). tele 갱신을 확인하세요.`
    }
    await loadTimes()
  } catch (e) {
    err.value = e.message || String(e)
  } finally {
    syncing.value = false
  }
}

onMounted(() => {
  tickOpNow()
  tickTimer = setInterval(tickOpNow, 1000)
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
        <span class="cf-clock-lab">운영 시각(Pi·KST)</span>
        <span class="cf-clock-val">{{ opNow }}</span>
      </div>
      <div class="cf-clock-item">
        <span class="cf-clock-lab">Pi 상태(동기)</span>
        <span class="cf-clock-val">{{ piNow }}</span>
        <span v-if="piTz" class="cf-clock-sub">{{ piTz }}</span>
      </div>
      <div class="cf-clock-item">
        <span class="cf-clock-lab">제어(tele 수신)</span>
        <span class="cf-clock-val">{{ controlNow }}</span>
        <span
          v-if="r4Online === true"
          class="cf-clock-sub cf-mqtt-pill cf-mqtt-pill--on"
        >R4 online</span>
        <span
          v-else-if="r4Online === false"
          class="cf-clock-sub cf-mqtt-pill cf-mqtt-pill--off"
        >
          R4 offline
          <template v-if="teleStaleSec != null"> · tele {{ teleStaleSec }}초 전</template>
        </span>
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
      <button
        type="button"
        class="btn btn-sm"
        :class="{ 'is-busy': refreshing }"
        :disabled="syncing || refreshing"
        @click="refreshTimes"
      >
        {{ refreshing ? '새로고침 중…' : '새로고침' }}
      </button>
      <button
        type="button"
        class="btn btn-sm btn-prim"
        :class="{ 'is-busy': syncing }"
        :disabled="syncing || refreshing"
        @click="syncRtc"
      >
        {{ syncing ? 'RTC 동기 중…' : 'Pi 시각 → Arduino RTC' }}
      </button>
    </div>
    <p v-if="err" class="cf-clock-err">{{ err }}</p>
    <p v-else-if="syncMsg" class="cf-clock-warn">{{ syncMsg }}</p>
    <p v-else class="cf-clock-hint">
      패널 LCD는 Arduino RTC(24시간)를 표시합니다. R4가 online일 때만 「Pi 시각 → Arduino RTC」가 반영됩니다.
    </p>
  </div>
</template>
