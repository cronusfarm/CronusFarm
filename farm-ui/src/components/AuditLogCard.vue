<script setup>
import { onMounted, ref } from 'vue'
import { useDevice } from '@/composables/useDevice'
import { apiJson } from '@/api/cronusfarm'
import { CF_SCH_CHANNELS } from '@/constants/channels'

const { deviceId, persist } = useDevice()
const auditRows = ref([])
const auditErr = ref('')
const auditOk = ref('')
const auditCh = ref('')
const auditLimit = ref(120)

const allChannels = CF_SCH_CHANNELS

function fmtTs(ms) {
  if (!ms) return '-'
  return new Date(ms).toLocaleString('ko-KR')
}
function fmtAut(pa, na) {
  if (pa < 0 && na < 0) return '-'
  if (pa < 0) return na ? '자동' : '수동'
  if (na < 0) return '-'
  return `${pa ? '자동' : '수동'}→${na ? '자동' : '수동'}`
}
function fmtOut(ps, ns) {
  if (ps < 0 && ns < 0) return '-'
  return `${ps >= 0 ? (ps ? 'ON' : 'OFF') : '?'}→${ns >= 0 ? (ns ? 'ON' : 'OFF') : '?'}`
}
function metaBrief(m) {
  if (!m) return ''
  try {
    const o = typeof m === 'string' ? JSON.parse(m) : m
    return o.action || o.hold_minutes != null ? `hold=${o.hold_minutes}m` : JSON.stringify(o).slice(0, 80)
  } catch {
    return String(m).slice(0, 80)
  }
}

async function loadAudit() {
  auditErr.value = ''
  auditOk.value = ''
  persist()
  try {
    const lim = Math.min(500, Math.max(10, parseInt(auditLimit.value, 10) || 120))
    let path = `/api/audit_log?device_id=${encodeURIComponent(deviceId.value)}&limit=${lim}`
    if (auditCh.value) path += `&channel=${encodeURIComponent(auditCh.value)}`
    const j = await apiJson(path)
    auditRows.value = j.rows || []
    auditOk.value = `${auditRows.value.length}건`
  } catch (e) {
    auditErr.value = e.message || String(e)
  }
}

async function backfillTimeline() {
  auditErr.value = ''
  auditOk.value = ''
  try {
    const j = await apiJson('/api/channel/backfill', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      body: JSON.stringify({
        device_id: deviceId.value,
        channel: auditCh.value || allChannels[0] || 'led_a1',
        hours: 72,
      }),
    })
    auditOk.value = `백필 삽입 ${j.inserted != null ? j.inserted : '?'}건`
    await loadAudit()
  } catch (e) {
    auditErr.value = e.message || String(e)
  }
}

onMounted(() => {
  loadAudit()
})

defineExpose({ loadAudit })
</script>

<template>
  <div class="cf-audit-card">
    <div class="row2">
      <label>
        채널
        <select v-model="auditCh">
          <option value="">(전체)</option>
          <option v-for="c in allChannels" :key="'aud' + c" :value="c">{{ c }}</option>
        </select>
      </label>
      <label>건수 <input v-model.number="auditLimit" type="number" min="10" max="500" style="width: 64px" /></label>
      <button type="button" class="btn" @click="loadAudit">새로고침</button>
      <button type="button" class="btn btn-prim" @click="backfillTimeline">타임라인 백필</button>
    </div>
    <div v-if="auditErr" class="err">{{ auditErr }}</div>
    <div v-if="auditOk" class="ok" style="font-size: 11px">{{ auditOk }}</div>
    <table class="tbl">
      <thead>
        <tr>
          <th>시간</th>
          <th>채널</th>
          <th>출처</th>
          <th>자동</th>
          <th>출력</th>
          <th>비고</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in auditRows" :key="r.id">
          <td>{{ fmtTs(r.ts_ms) }}</td>
          <td>{{ r.channel_key }}</td>
          <td>{{ r.source }}</td>
          <td>{{ fmtAut(r.prev_auto, r.new_auto) }}</td>
          <td>{{ fmtOut(r.prev_state, r.new_state) }}</td>
          <td>{{ metaBrief(r.meta) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>