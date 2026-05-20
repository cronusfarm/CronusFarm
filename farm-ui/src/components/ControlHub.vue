<script setup>
import { ref } from 'vue'
import { apiUrl } from '@/api/cronusfarm'
import { useDevice } from '@/composables/useDevice'

const { deviceId } = useDevice()

const rows = ref([
  { label: '목표 pH', topic: 'ctl_target_ph', min: 0, max: 14, step: 0.1, v: 7.0 },
  { label: '목표 EC (mS/cm)', topic: 'ctl_target_ec', min: 0, max: 3, step: 0.05, v: 1.0 },
  { label: '목표 온도 (°C)', topic: 'ctl_target_temp_c', min: 10, max: 35, step: 0.5, v: 25.0 },
  { label: '목표 습도 (%)', topic: 'ctl_target_rh_pct', min: 30, max: 90, step: 1, v: 60 },
  { label: '사진 촬영 주기 cam01 (분)', topic: 'cctv_cam01_interval_min', min: 1, max: 720, step: 1, v: 60 },
])

function fmt(r) {
  const x = Number(r.v)
  if (!Number.isFinite(x)) return '-'
  if (Math.abs(r.step) >= 1) return String(Math.round(x))
  return String(Math.round(x * 1000) / 1000).replace(/\.0+$/, '')
}

async function push(r) {
  const v = Number(r.v)
  if (!Number.isFinite(v)) return
  try {
    await fetch(apiUrl('/settings/kv'), {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      body: JSON.stringify({
        device_id: deviceId.value,
        key: r.topic,
        value: String(v),
      }),
    })
  } catch (e) {
    console.warn(e)
  }
}
</script>

<template>
  <div class="cf2-ctlhub">
    <div class="cf-ctl-hub">
      <div class="t">스마트팜 관제 허브</div>
      <div class="s">
        목표 pH·EC·온도·습도를 설정하면 SQLite <code>settings_kv</code>에 저장됩니다. 시계열은 Grafana에서
        확인하세요.
      </div>
      <div class="badges">
        <span class="bd">Influx: tele + guard_*</span>
        <span class="bd">SQLite: 이력·설정</span>
        <span class="bd">DEVICE_ID: flow.deviceId</span>
      </div>
    </div>
    <div v-for="r in rows" :key="r.topic" class="cf2-slrow">
      <div class="cf2-sllab">{{ r.label }}</div>
      <input
        v-model.number="r.v"
        class="cf2-sl"
        type="range"
        :min="r.min"
        :max="r.max"
        :step="r.step"
        @change="push(r)"
      />
      <div class="cf2-slval">{{ fmt(r) }}</div>
    </div>
    <div class="cf2-hint">슬라이더를 놓을 때(change) SQLite 브리지로 전송됩니다.</div>
  </div>
</template>
