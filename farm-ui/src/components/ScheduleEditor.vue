<script setup>
import { computed, watch } from 'vue'
import { CF_SCH_CHANNELS } from '@/constants/channels'
import { API_BASE } from '@/api/cronusfarm'
import { useDevice } from '@/composables/useDevice'
import { useScheduleEditor } from '@/composables/useScheduleEditor'
import SchedulePumpHelp from '@/components/SchedulePumpHelp.vue'

const props = defineProps({
  initialChannel: { type: String, default: '' },
  /** SettingsAllView 등 상위에 제목·카드가 있을 때 내부 박스·중복 제목 제거 */
  embedded: { type: Boolean, default: false },
})

const channel = defineModel('channel', { type: String, default: 'led_a1' })
const { deviceId } = useDevice()

if (props.initialChannel) {
  channel.value = props.initialChannel
}

const {
  dayMeta,
  enableWindow,
  enableCycle,
  scheduleKind,
  togetherSlots,
  eachDayRows,
  cycleSlots,
  loading,
  err,
  msg,
  pickAllDays,
  addTogether,
  dropTogether,
  addCycle,
  dropCycle,
  loadSch,
  saveSch,
} = useScheduleEditor(
  () => deviceId.value,
  () => channel.value,
)

defineExpose({ loadSch })

watch(channel, () => {
  loadSch()
})

const channels = CF_SCH_CHANNELS
const isPumpAbWindow = computed(() => /^pump_(a[12]|b[12])$/.test(channel.value))

function fmtDur(m, s) {
  const mm = Math.max(0, parseInt(m, 10) || 0)
  const ss = Math.max(0, Math.min(59, parseInt(s, 10) || 0))
  if (mm && ss) return `${mm}분 ${ss}초`
  if (mm) return `${mm}분`
  if (ss) return `${ss}초`
  return '0초'
}

function cycleSummary(c) {
  const on = fmtDur(c.onM, c.onS)
  const off = fmtDur(c.offM, c.offS)
  const period = on + ' 켜짐 · ' + off + ' 꺼짐 반복'
  if (!c.useWinLimit) return '하루 종일 · ' + period
  return `${c.winOnStr || '00:00'}~${c.winOffStr || '24:00'} 사이만 · ` + period
}

function selectedDayLabels(days) {
  const labels = dayMeta.map((d, i) => (days[i] ? d.label : null)).filter(Boolean)
  if (labels.length === 7) return '매일'
  if (!labels.length) return '요일 없음'
  return labels.join('·')
}
</script>

<template>
  <div :class="embedded ? 'cf2-schedule-embed' : 'cf2-schedule'">
    <p class="cf2-sch-sub">
      <strong>저장</strong> 시 SQLite <code class="cf2-sch-code">schedule_rule</code> → MQTT
      <code class="cf2-sch-code">SCHED_JSON</code> → Arduino. 시간대·주기를 같이 켜면 OR(합집합)으로 동작합니다.
    </p>

    <div class="cf2-sch-bar">
      <label class="cf2-sch-lab">
        채널
        <select v-model="channel" class="cf2-sch-sel">
          <option v-for="c in channels" :key="c" :value="c">{{ c }}</option>
        </select>
      </label>
    </div>

    <div class="cf2-sch-actions">
      <button type="button" class="cf2-sch-btn" :disabled="loading" @click="loadSch">불러오기</button>
      <button type="button" class="cf2-sch-btn cf2-sch-prim" :disabled="loading" @click="saveSch">
        저장 (DB + MQTT)
      </button>
    </div>

    <div v-if="err" class="cf2-sch-err">{{ err }}</div>
    <div v-if="msg" class="cf2-sch-msg">{{ msg }}</div>

    <!-- ① 시간대: 계속 켜짐 -->
    <section class="cf2-sch-panel">
      <label class="cf2-sch-sec-hd">
        <input v-model="enableWindow" type="checkbox" />
        ① 하루 중 「계속 켜짐」 구간
      </label>
      <p class="cf2-sch-hint">
        LED 등: 지정 시각부터 꺼질 때까지 릴레이를 계속 ON. (예: 06:00~22:00 조명)
      </p>
      <template v-if="enableWindow">
        <div class="cf2-sch-subm">
          <label class="cf2-sch-radio">
            <input v-model="scheduleKind" type="radio" value="together" />
            여러 요일 · 같은 시간
          </label>
          <label class="cf2-sch-radio">
            <input v-model="scheduleKind" type="radio" value="eachDay" />
            요일마다 다른 시간
          </label>
        </div>
        <div v-if="scheduleKind === 'together'" class="cf2-sch-tblwrap">
          <table class="cf2-sch-tbl">
            <thead>
              <tr>
                <th>적용 요일</th>
                <th>켜지는 시각</th>
                <th>꺼지는 시각</th>
                <th>사용</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(s, idx) in togetherSlots" :key="'tg' + idx">
                <td class="cf2-sch-days">
                  <label v-for="(d, di) in dayMeta" :key="d.bit" class="cf2-sch-daycb">
                    <input v-model="s.days[di]" type="checkbox" /> {{ d.label }}
                  </label>
                  <button type="button" class="cf2-sch-mini" @click="pickAllDays(s)">전체</button>
                </td>
                <td><input v-model="s.onStr" class="cf2-sch-time" type="time" step="60" /></td>
                <td><input v-model="s.offStr" class="cf2-sch-time" type="time" step="60" /></td>
                <td class="cf2-sch-cen">
                  <input v-model="s.enabled" type="checkbox" :true-value="1" :false-value="0" />
                </td>
                <td>
                  <button
                    type="button"
                    class="cf2-sch-x"
                    :disabled="togetherSlots.length <= 1"
                    @click="dropTogether(idx)"
                  >
                    삭제
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
          <button type="button" class="cf2-sch-add" @click="addTogether">+ 켜짐 구간 추가</button>
        </div>
        <div v-else>
          <table class="cf2-sch-tbl">
            <thead>
              <tr>
                <th>요일</th>
                <th>켜지는 시각</th>
                <th>꺼지는 시각</th>
                <th>사용</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in eachDayRows" :key="row.bit">
                <td class="cf2-sch-dname">{{ row.label }}</td>
                <td><input v-model="row.onStr" class="cf2-sch-time" type="time" step="60" /></td>
                <td><input v-model="row.offStr" class="cf2-sch-time" type="time" step="60" /></td>
                <td class="cf2-sch-cen">
                  <input v-model="row.enabled" type="checkbox" :true-value="1" :false-value="0" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </section>

    <!-- ② 주기: ON/OFF 반복 -->
    <section class="cf2-sch-panel">
      <label class="cf2-sch-sec-hd">
        <input v-model="enableCycle" type="checkbox" />
        ② 「켜짐·꺼짐」을 짧게 반복 (펌프·미스트)
      </label>
      <p class="cf2-sch-hint">
        예: 30초 켜고 30초 끄기를 반복. 「지정 시간만」을 고르면 그 구간 안에서만 반복합니다.
      </p>
      <template v-if="enableCycle">
        <div class="cf2-sch-cycle-list">
          <article
            v-for="(c, cidx) in cycleSlots"
            :key="'cy' + cidx"
            class="cf2-sch-cycle-card"
            :class="{ off: !c.enabled }"
          >
            <header class="cf2-sch-cycle-hd">
              <span class="cf2-sch-cycle-title">반복 규칙 {{ cidx + 1 }}</span>
              <label class="cf2-sch-cycle-use">
                <input v-model="c.enabled" type="checkbox" :true-value="1" :false-value="0" />
                사용
              </label>
              <button
                type="button"
                class="cf2-sch-x"
                :disabled="cycleSlots.length <= 1"
                title="이 규칙 삭제"
                @click="dropCycle(cidx)"
              >
                삭제
              </button>
            </header>

            <p class="cf2-sch-cycle-sum">{{ cycleSummary(c) }}</p>

            <div class="cf2-sch-field">
              <span class="cf2-sch-field-lab">적용 요일</span>
              <div class="cf2-sch-days cf2-sch-days-inline">
                <label v-for="(d, di) in dayMeta" :key="d.bit" class="cf2-sch-daycb">
                  <input v-model="c.days[di]" type="checkbox" /> {{ d.label }}
                </label>
                <button type="button" class="cf2-sch-mini" @click="pickAllDays(c)">전체</button>
              </div>
              <span class="cf2-sch-field-note">{{ selectedDayLabels(c.days) }}</span>
            </div>

            <div class="cf2-sch-field">
              <span class="cf2-sch-field-lab">한 번 켜짐</span>
              <div class="cf2-sch-dur">
                <label class="cf2-sch-dur-u">
                  <input v-model.number="c.onM" class="cf2-sch-num" type="number" min="0" max="1440" />
                  분
                </label>
                <label class="cf2-sch-dur-u">
                  <input v-model.number="c.onS" class="cf2-sch-num" type="number" min="0" max="59" />
                  초
                </label>
              </div>
            </div>

            <div class="cf2-sch-field">
              <span class="cf2-sch-field-lab">한 번 꺼짐</span>
              <div class="cf2-sch-dur">
                <label class="cf2-sch-dur-u">
                  <input v-model.number="c.offM" class="cf2-sch-num" type="number" min="0" max="1440" />
                  분
                </label>
                <label class="cf2-sch-dur-u">
                  <input v-model.number="c.offS" class="cf2-sch-num" type="number" min="0" max="59" />
                  초
                </label>
              </div>
            </div>

            <div class="cf2-sch-field cf2-sch-field-scope">
              <span class="cf2-sch-field-lab">언제 반복할까요?</span>
              <div class="cf2-sch-scope-radios">
                <label class="cf2-sch-radio">
                  <input v-model="c.useWinLimit" type="radio" :value="false" />
                  하루 종일
                </label>
                <label class="cf2-sch-radio">
                  <input v-model="c.useWinLimit" type="radio" :value="true" />
                  아래 시각 사이만
                </label>
              </div>
              <div v-if="c.useWinLimit" class="cf2-sch-win-range">
                <label class="cf2-sch-win-l">
                  시작
                  <input v-model="c.winOnStr" class="cf2-sch-time" type="time" step="60" />
                </label>
                <span class="cf2-sch-win-sep">~</span>
                <label class="cf2-sch-win-l">
                  끝
                  <input v-model="c.winOffStr" class="cf2-sch-time" type="time" step="60" />
                </label>
              </div>
            </div>
          </article>
        </div>
        <button type="button" class="cf2-sch-add" @click="addCycle">+ 반복 규칙 추가</button>
      </template>
    </section>

    <SchedulePumpHelp v-if="isPumpAbWindow && enableCycle" />

    <div class="cf2-sch-foot">
      불러오기 실패: <code class="cf2-sch-code">cronusfarm-sqlite-bridge</code> (18766) · API
      <code class="cf2-sch-code">{{ API_BASE }}/api/schedule</code>
    </div>
  </div>
</template>
