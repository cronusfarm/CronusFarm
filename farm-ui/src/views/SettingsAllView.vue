<script setup>

import { onMounted, ref } from 'vue'

import BedsView from '@/views/BedsView.vue'

import ScheduleOverviewView from '@/views/ScheduleOverviewView.vue'

import ScheduleEditor from '@/components/ScheduleEditor.vue'

import ScheduleDefaultsTable from '@/components/ScheduleDefaultsTable.vue'

import ControlHub from '@/components/ControlHub.vue'

import AuditLogCard from '@/components/AuditLogCard.vue'

import ClockStatusBar from '@/components/ClockStatusBar.vue'
import SettingsResetBar from '@/components/SettingsResetBar.vue'

import { useDevice } from '@/composables/useDevice'

import { useScheduleBatch } from '@/composables/useScheduleBatch'

import { ensureChartClockPolling } from '@/composables/useChartClock'

import { apiJson } from '@/api/cronusfarm'



const { deviceId, persist } = useDevice()

const { loadSchedules: fetchScheduleBatch, invalidate } = useScheduleBatch()

const editChannel = ref('led_a1')

const syncMsg = ref('')

const syncErr = ref('')

const syncBusy = ref('')

const refreshBusy = ref(false)

const editorRef = ref(null)

const bedsRef = ref(null)

const schedRef = ref(null)

const auditRef = ref(null)



function onPickChannel(ch) {

  editChannel.value = ch

  const el = document.getElementById('sec-sched-edit')

  el?.scrollIntoView({ behavior: 'smooth', block: 'start' })

  setTimeout(() => editorRef.value?.loadSch?.(), 200)

}



async function syncSchedulesToDevice() {

  syncErr.value = ''

  syncMsg.value = ''

  syncBusy.value = 'sync'

  persist()

  try {

    const fa = await apiJson(
      `/api/device/force_all_auto?device_id=${encodeURIComponent(deviceId.value)}`,
    )
    const j = await apiJson(
      `/api/schedule/sync_device?device_id=${encodeURIComponent(deviceId.value)}`,
    )

    syncMsg.value = `전체 AUTO: 펌웨어 ${fa.auto_published ?? 0}채널 · 재동기화 ${j.channels_published ?? 0}채널`

    invalidate()

    await fetchScheduleBatch(deviceId.value, { force: true })

    editorRef.value?.loadSch?.()

    bedsRef.value?.poll?.()

    bedsRef.value?.loadSchedules?.()

    schedRef.value?.loadAll?.()

  } catch (e) {

    const msg = e.message || String(e)

    if (msg.includes('404')) {

      syncErr.value =

        'HTTP 404 — API 경로 없음. Pi nginx에 /farm/cronusfarm-sqlite → 브리지(18766) 프록시 적용 후 reload 하세요.'

    } else {

      syncErr.value = msg

    }

  } finally {

    syncBusy.value = ''

  }

}



async function refreshPage() {

  refreshBusy.value = true

  try {

    invalidate()

    await fetchScheduleBatch(deviceId.value, { force: true })

    bedsRef.value?.poll?.()

    bedsRef.value?.loadSchedules?.()

    schedRef.value?.loadAll?.()

    auditRef.value?.loadAudit?.()

    syncMsg.value = '전체 새로고침 완료'

    syncErr.value = ''

  } catch (e) {

    syncErr.value = e.message || String(e)

  } finally {

    refreshBusy.value = false

  }

}



async function ensureAutoUnlessHold() {

  try {

    await apiJson('/api/device/ensure_auto_mode', {

      method: 'POST',

      headers: { 'Content-Type': 'application/json; charset=utf-8' },

      body: JSON.stringify({ device_id: deviceId.value }),

    })

  } catch (e) {

    console.warn('ensure_auto_mode', e)

  }

}



onMounted(() => {
  persist()
  ensureChartClockPolling()
  void ensureAutoUnlessHold()
  void fetchScheduleBatch(deviceId.value).then(() => {
    schedRef.value?.loadAll?.()
    bedsRef.value?.loadSchedules?.()
  })
  bedsRef.value?.poll?.()
  setTimeout(() => auditRef.value?.loadAudit?.(), 1200)
})

</script>



<template>

  <div class="cf-settings-all">

    <ClockStatusBar />



    <div class="cf-settings-toolbar">

      <div class="cf-sync-block">

        <button
          type="button"
          class="btn btn-prim"
          :class="{ 'is-busy': syncBusy === 'sync' }"
          :disabled="!!syncBusy || refreshBusy"
          @click="syncSchedulesToDevice"
        >
          {{ syncBusy === 'sync' ? '재동기화 중…' : '전체 채널 재동기화 (선택)' }}
        </button>

        <p class="cf-sync-help">

          <strong>저장</strong> = DB 반영 + 해당 채널 즉시 MQTT(SCHED_JSON).

          <strong>재동기화</strong> = DB에 있는 모든 채널을 한 번에 다시 보냄(부팅·복구용).

          수동 ON/OFF는 아래 <strong>채널별 제어</strong> 또는 R3 패널 엔코더.

        </p>

      </div>

      <button
        type="button"
        class="btn btn-sm"
        :class="{ 'is-busy': refreshBusy }"
        :disabled="refreshBusy || !!syncBusy"
        @click="refreshPage"
      >
        {{ refreshBusy ? '새로고침 중…' : '전체 새로고침' }}
      </button>

      <span v-if="syncMsg" class="ok">{{ syncMsg }}</span>

      <span v-if="syncErr" class="err">{{ syncErr }}</span>

      <SettingsResetBar />

    </div>



    <div class="cf-split-top">
      <section id="sec-beds" class="cf-split-col">
        <div class="cf-sec-hd cf-sec-hd--paired">
          <div class="cf-sec-hd-body">
            <h2 class="cf-sec-title">채널별 제어</h2>
            <p class="cf-sec-hd-sub cf-sec-hd-sub--ghost">
              계획 ON/OFF=지금 스케줄 · ON/OFF 버튼=tele 출력 · 자동=스케줄 따름
            </p>
          </div>
        </div>
        <BedsView ref="bedsRef" embedded />
      </section>

      <section id="sec-sched-24h" class="cf-split-col">
        <div class="cf-sec-hd cf-sec-hd--paired">
          <div class="cf-sec-hd-body">
            <h2 class="cf-sec-title">채널별 스케줄(24H)</h2>
            <div class="cf-sch-legend-bar" role="note">
              <span class="lg lg-sch">스케줄(계획)</span>
              <span class="lg lg-tele">실제(tele)</span>
            </div>
          </div>
          <button type="button" class="btn btn-sm" @click="schedRef?.loadAll?.()">새로고침</button>
        </div>
        <ScheduleOverviewView ref="schedRef" embedded @pick-channel="onPickChannel" />
      </section>
    </div>

    <div class="cf-split-top">
      <section id="sec-sched-edit" class="cf-split-col">
        <div class="cf-sec-hd cf-sec-hd--paired">
          <h2 class="cf-sec-title">채널별 스케줄 편집</h2>
        </div>
        <div class="cf-settings-shell cf-settings-shell--wide">
          <ScheduleEditor ref="editorRef" v-model:channel="editChannel" embedded />
        </div>
      </section>

      <section id="sec-sched-defaults" class="cf-split-col">
        <div class="cf-sec-hd cf-sec-hd--paired">
          <h2 class="cf-sec-title">기본 스케줄표</h2>
        </div>
        <div class="cf-settings-shell cf-settings-shell--wide">
          <ScheduleDefaultsTable />
        </div>
      </section>
    </div>



    <section id="sec-control" class="cf-sec-block">

      <div class="cf-sec-hd cf-sec-hd--paired">

        <h2 class="cf-sec-title">관제</h2>

      </div>

      <div class="cf-settings-shell cf-settings-shell--wide">

        <ControlHub />

      </div>

    </section>



    <section id="sec-audit" class="cf-sec-block">

      <div class="cf-sec-hd cf-sec-hd--paired">

        <h2 class="cf-sec-title">제어 감사</h2>

      </div>

      <div class="cf-settings-shell cf-settings-shell--wide">

        <AuditLogCard ref="auditRef" />

      </div>

    </section>

  </div>

</template>

