<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { CF_SCH_CHANNELS } from '@/constants/channels'
import { channelKind, channelLabel } from '@/constants/channelLabels'
import { channelIconSvg } from '@/lib/channelIcons'
import { useDevice } from '@/composables/useDevice'
import { useScheduleBatch } from '@/composables/useScheduleBatch'
import {
  ensureChartClockPolling,
  stopChartClockPolling,
} from '@/composables/useChartClock'
import { apiUrl } from '@/api/cronusfarm'
import Sch24hChart from '@/components/Sch24hChart.vue'

const { embedded } = defineProps({
  embedded: { type: Boolean, default: false },
})

const emit = defineEmits(['pick-channel'])
const { deviceId, persist } = useDevice()
const { rulesFor } = useScheduleBatch()
const rows = ref(CF_SCH_CHANNELS.map((k) => ({ key: k, rules: [], tl: null })))
const dayWindow = ref(null)
const loading = ref(false)
let devTimer = null
let pollTimer = null

function pickChannel(ch) {
  emit('pick-channel', ch)
}

async function loadAll() {
  loading.value = true
  persist()
  const tlUrl =
    `${apiUrl('/api/channel/timeline/batch')}?device_id=${encodeURIComponent(deviceId.value)}` +
    `&channels=${encodeURIComponent(CF_SCH_CHANNELS.join(','))}&hours=12`
  let tlMap = {}
  try {
    const ac = new AbortController()
    const t = setTimeout(() => ac.abort(), 15000)
    const tr = await fetch(tlUrl, { credentials: 'same-origin', signal: ac.signal })
    clearTimeout(t)
    if (tr.ok) {
      const tj = await tr.json()
      tlMap = tj.channels || {}
      if (tj.day_window) dayWindow.value = tj.day_window
    }
  } catch (e) {
    console.warn(e)
  }
  rows.value = CF_SCH_CHANNELS.map((key) => ({
    key,
    rules: rulesFor(key),
    tl: tlMap[key] || null,
  }))
  loading.value = false
}

onMounted(() => {
  ensureChartClockPolling()
  loadAll()
  pollTimer = setInterval(() => loadAll(), 60000)
  devTimer = setInterval(() => {
    try {
      const s = localStorage.getItem('cfDeviceId')
      if (s && s.trim() && s.trim() !== deviceId.value) {
        deviceId.value = s.trim()
        loadAll()
      }
    } catch {
      /* ignore */
    }
  }, 60000)
})

onUnmounted(() => {
  if (devTimer) clearInterval(devTimer)
  if (pollTimer) clearInterval(pollTimer)
  stopChartClockPolling()
})

defineExpose({ loadAll })
</script>

<template>
  <div
    :class="[
      embedded ? 'cf-sch-overview-embed' : 'cf-settings-shell',
      'cf-sch-overview-page',
    ]"
  >
    <div v-if="loading" class="cf-sch-overview-loading">타임라인 불러오는 중…</div>

    <div class="cf-sch-overview-list">
      <div
        v-for="row in rows"
        :key="row.key"
        class="cf-sch-overview-row"
        @click="pickChannel(row.key)"
      >
        <div class="cf-sch-overview-meta">
          <span class="cf-sch-overview-ic" v-html="channelIconSvg(channelKind(row.key), 22)" />
          <span class="cf-sch-overview-lbl">{{ channelLabel(row.key) }}</span>
        </div>
        <div class="cf-sch-overview-cwrap">
          <Sch24hChart
            :rules="row.rules"
            :exec-data="row.tl"
            :day-window="dayWindow"
            show-time-axis
          />
        </div>
      </div>
    </div>
    <p v-if="!embedded" class="hint">행 클릭 → 「채널별 스케줄 편집」</p>
  </div>
</template>
