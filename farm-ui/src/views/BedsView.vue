<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { BEDS, CF_SCH_CHANNELS } from '@/constants/channels'
import { useDevice } from '@/composables/useDevice'
import { apiUrl } from '@/api/cronusfarm'
import { channelIconSvg } from '@/lib/channelIcons'
import { isScheduleOnAt } from '@/lib/scheduleCanvas'
import { useScheduleBatch } from '@/composables/useScheduleBatch'
import { usePiClock } from '@/composables/usePiClock'

const { embedded } = defineProps({
  embedded: { type: Boolean, default: false },
})

const { deviceId, persist } = useDevice()
const status = ref({ channels: {} })
const { loadSchedules: fetchScheduleBatch, rulesFor, rulesByChannel } = useScheduleBatch()
const holdMin = ref({})
const holdOptions = Array.from({ length: 60 }, (_, i) => i + 1)
let pollTimer = null

const channelMeta = computed(() => {
  const m = Object.create(null)
  for (const bed of BEDS) {
    for (const ch of bed.channels) {
      m[ch.key] = { ...ch, bedTitle: bed.title }
    }
  }
  return m
})

/** 24h 그래프와 동일 채널 순서 */
const orderedRows = computed(() =>
  CF_SCH_CHANNELS.map((key) => {
    const meta = channelMeta.value[key]
    if (!meta) return null
    return { key, ...meta }
  }).filter(Boolean),
)

const allChannels = computed(() => orderedRows.value.map((r) => r.key))

function chSt(k) {
  return status.value.channels[k] || {}
}
function isOn(k) {
  return Number(chSt(k).state) === 1
}
function isAuto(k) {
  const st = chSt(k)
  if (st.display_mode === 'manual') return false
  if (st.display_mode === 'auto') return true
  const exp = st.hold_expires_ms
  if (exp != null && Number(exp) > Date.now()) return false
  const v = st.auto_mode
  if (v === undefined || v === null) return true
  return Number(v) === 1
}
const { piNowMs } = usePiClock()

function schNow(k) {
  return isScheduleOnAt(rulesFor(k), piNowMs())
}

function fmtKstHm(ms) {
  if (ms == null || !Number.isFinite(Number(ms))) return ''
  return new Intl.DateTimeFormat('ko-KR', {
    timeZone: 'Asia/Seoul',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(Number(ms)))
}

function rowHint(k) {
  const sn = schNow(k)
  const on = isOn(k)
  const auto = isAuto(k)
  const hold = holdMin.value[k] || 30
  const teleAt = fmtKstHm(chSt(k).tele_ts_ms ?? chSt(k).ts_ms)
  if (!auto && !on && sn) {
    return `수동 OFF · 스케줄은 지금 ON${teleAt ? ` · tele ${teleAt}` : ''} → 「자동」으로 스케줄대로 켜짐`
  }
  if (!auto && on && !sn) {
    return `수동 ON · 스케줄은 지금 OFF → 「자동」 누르면 스케줄대로 꺼짐`
  }
  if (!auto && sn) {
    return `수동(최대 ${hold}분 후 자동) · 스케줄 ON · 「자동」으로 복귀`
  }
  if (auto && sn && !on) return '자동 · 스케줄 ON · 릴레이 OFF(tele)'
  if (auto && !sn && on) {
    return '자동 · 스케줄 OFF인데 출력 ON → 「전체 재동기화」 또는 수동 전환 확인'
  }
  if (auto && !sn && !on) return ''
  return ''
}

/** 노란 경고 행: 수동·스케줄 불일치만 */
function rowWarn(k) {
  const auto = isAuto(k)
  const sn = schNow(k)
  const on = isOn(k)
  if (!auto && on && !sn) return true
  if (!auto && sn) return true
  if (auto && sn && !on) return true
  if (auto && !sn && on) return true
  return false
}

async function loadSchedules() {
  await fetchScheduleBatch(deviceId.value)
}

async function poll() {
  persist()
  try {
    const u = `${apiUrl('/api/channel/status')}?device_id=${encodeURIComponent(deviceId.value)}`
    const r = await fetch(u, { credentials: 'same-origin' })
    if (!r.ok) throw new Error('status HTTP ' + r.status)
    const j = await r.json()
    status.value = j
    for (const [k, v] of Object.entries(j.channels || {})) {
      if (v?.hold_minutes != null) holdMin.value[k] = Number(v.hold_minutes)
    }
  } catch (e) {
    console.warn(e)
  }
}

async function postAction(body) {
  const r = await fetch(apiUrl('/api/channel-action'), {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
    body: JSON.stringify({ ...body, device_id: deviceId.value }),
  })
  const j = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(j.error || 'HTTP ' + r.status)
  await poll()
}

async function toggleOut(k) {
  if (isAuto(k)) return
  const on = !isOn(k)
  await postAction({
    channel: k,
    action: 'set_output',
    on,
    new_state: on ? 1 : 0,
    new_auto: 0,
    hold_minutes: holdMin.value[k] || 30,
    prev_auto: chSt(k).auto_mode,
    prev_state: chSt(k).state,
  })
}

async function toggleMode(k) {
  const out = isOn(k) ? 1 : 0
  if (isAuto(k)) {
    await postAction({
      channel: k,
      action: 'set_manual',
      hold_minutes: holdMin.value[k] || 30,
      prev_auto: 1,
      new_auto: 0,
      new_state: out,
      prev_state: chSt(k).state ?? out,
    })
  } else {
    await postAction({ channel: k, action: 'set_auto', prev_auto: 0, new_auto: 1 })
  }
}

async function reapplyHold(k) {
  if (isAuto(k)) return
  const out = isOn(k) ? 1 : 0
  await postAction({
    channel: k,
    action: 'set_manual',
    hold_minutes: holdMin.value[k] || 30,
    prev_auto: 0,
    new_auto: 0,
    new_state: out,
    prev_state: out,
  })
}

onMounted(() => {
  for (const k of allChannels.value) {
    if (holdMin.value[k] == null) holdMin.value[k] = 30
  }
  void loadSchedules(deviceId.value)
  void poll()
  pollTimer = setInterval(() => {
    poll()
  }, 10000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})

defineExpose({ poll, loadSchedules })
</script>

<template>
  <div :class="embedded ? 'cf-beds-embed' : 'cf-settings-shell'">
    <div v-if="!embedded" class="row2 cf-ch-toolbar">
      <button type="button" class="btn" @click="poll(); loadSchedules()">상태 새로고침</button>
    </div>

    <div class="cf-ch-list">
      <div
        v-for="row in orderedRows"
        :key="row.key"
        class="ch-row"
        :class="{ 'ch-row-warn': rowWarn(row.key), 'ch-row-info': rowHint(row.key) && !rowWarn(row.key) }"
      >
        <span class="ic" v-html="channelIconSvg(row.kind, 22)" />
        <div class="ch-meta">
          <span class="ch-name">{{ row.label }}</span>
          <span class="ch-pin">{{ row.pin }}</span>
          <span
            class="ch-sch-now"
            :class="schNow(row.key) ? 'on' : 'off'"
            :title="'지금 시각(KST) 기준 DB 스케줄이 켜져 있어야 하는지(계획). 자동/수동·실제 릴레이(ON 버튼)와는 별개'"
          >
            계획 {{ schNow(row.key) ? 'ON' : 'OFF' }}
          </span>
          <span v-if="rowHint(row.key)" class="ch-hint">{{ rowHint(row.key) }}</span>
        </div>
        <button
          type="button"
          class="sw-out"
          :class="{
            on: isOn(row.key),
            off: !isOn(row.key),
            'on-live': isAuto(row.key) && isOn(row.key),
          }"
          :disabled="isAuto(row.key)"
          :title="isAuto(row.key) ? '자동 · 스케줄/tele 기준 ON' : ''"
          @click="toggleOut(row.key)"
        >
          {{ isOn(row.key) ? 'ON' : 'OFF' }}
        </button>
        <button
          type="button"
          class="sw-am"
          :class="isAuto(row.key) ? 'auto' : 'manual'"
          @click="toggleMode(row.key)"
        >
          {{ isAuto(row.key) ? '자동' : '수동' }}
        </button>
        <label class="ch-hold" :class="{ disabled: isAuto(row.key) }">
          <span class="ch-hold-lbl">복귀</span>
          <select
            v-model.number="holdMin[row.key]"
            class="hold-sel"
            :disabled="isAuto(row.key)"
            @change="reapplyHold(row.key)"
          >
            <option v-for="m in holdOptions" :key="m" :value="m">{{ m }}분</option>
          </select>
        </label>
      </div>
    </div>
  </div>
</template>
