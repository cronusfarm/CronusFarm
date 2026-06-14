import { ref } from 'vue'
import { apiJson } from '@/api/cronusfarm'

const DAY_META = [
  { label: '월', bit: 1 },
  { label: '화', bit: 2 },
  { label: '수', bit: 4 },
  { label: '목', bit: 8 },
  { label: '금', bit: 16 },
  { label: '토', bit: 32 },
  { label: '일', bit: 64 },
]

function days7() {
  return [true, true, true, true, true, true, true]
}

function defaultTogetherSlot() {
  return { days: days7(), onStr: '06:00', offStr: '22:00', enabled: 1 }
}

function defaultCycleSlot() {
  return {
    days: days7(),
    onM: 0,
    onS: 30,
    offM: 0,
    offS: 30,
    useWinLimit: false,
    winOnStr: '09:00',
    winOffStr: '17:00',
    enabled: 1,
  }
}

function defaultEachDayRows() {
  return DAY_META.map((d) => ({
    label: d.label,
    bit: d.bit,
    onStr: '06:00',
    offStr: '22:00',
    enabled: 0,
  }))
}

export function useScheduleEditor(getDeviceId, getChannel) {
  const dayMeta = DAY_META
  const enableWindow = ref(true)
  const enableCycle = ref(true)
  const scheduleKind = ref('together')
  const togetherSlots = ref([defaultTogetherSlot()])
  const eachDayRows = ref(defaultEachDayRows())
  const cycleSlots = ref([defaultCycleSlot()])
  const loading = ref(false)
  const err = ref('')
  const msg = ref('')

  function minToTimeStr(m) {
    const n = Math.max(0, Math.min(1439, parseInt(m, 10) || 0))
    const hh = String(Math.floor(n / 60)).padStart(2, '0')
    const mm = String(n % 60).padStart(2, '0')
    return `${hh}:${mm}`
  }

  function timeStrToMin(s) {
    if (!s || typeof s !== 'string') return 0
    const p = s.split(':')
    let hh = parseInt(p[0], 10)
    let mm = parseInt(p[1], 10)
    if (Number.isNaN(hh)) hh = 0
    if (Number.isNaN(mm)) mm = 0
    hh = Math.max(0, Math.min(23, hh))
    mm = Math.max(0, Math.min(59, mm))
    return Math.min(1439, hh * 60 + mm)
  }

  function daysArrToMask(arr) {
    const bits = [1, 2, 4, 8, 16, 32, 64]
    let m = 0
    for (let i = 0; i < 7; i++) {
      if (arr[i]) m |= bits[i]
    }
    return m
  }

  function maskToDaysArr(mask) {
    const bits = [1, 2, 4, 8, 16, 32, 64]
    return bits.map((b) => !!(mask & b))
  }

  function pickAllDays(row) {
    for (let i = 0; i < 7; i++) row.days[i] = true
  }

  function addTogether() {
    togetherSlots.value.push(defaultTogetherSlot())
  }

  function dropTogether(idx) {
    if (togetherSlots.value.length <= 1) return
    togetherSlots.value.splice(idx, 1)
  }

  function addCycle() {
    cycleSlots.value.push(defaultCycleSlot())
  }

  function dropCycle(idx) {
    if (cycleSlots.value.length <= 1) return
    cycleSlots.value.splice(idx, 1)
  }

  function isPow2(m) {
    const x = parseInt(m, 10)
    return x > 0 && (x & (x - 1)) === 0
  }

  function partsToSec(minPart, secPart) {
    const mm = Math.max(0, parseInt(minPart, 10) || 0)
    let ss = Math.max(0, parseInt(secPart, 10) || 0)
    ss = Math.min(59, ss)
    return Math.min(86400, mm * 60 + ss)
  }

  function mapWindowRules(list) {
    const bits = [1, 2, 4, 8, 16, 32, 64]
    const labels = ['월', '화', '수', '목', '금', '토', '일']
    if (!list.length) {
      scheduleKind.value = 'together'
      togetherSlots.value = [defaultTogetherSlot()]
      eachDayRows.value = defaultEachDayRows()
      enableWindow.value = false
      return
    }
    enableWindow.value = true
    const onlyPow2 = list.every((r) => isPow2(r.dow_mask))
    if (onlyPow2 && list.length <= 7) {
      scheduleKind.value = 'eachDay'
      eachDayRows.value = bits.map((b, i) => {
        const hit = list.find((r) => parseInt(r.dow_mask, 10) === b)
        return {
          label: labels[i],
          bit: b,
          onStr: hit ? minToTimeStr(hit.on_min) : '06:00',
          offStr: hit ? minToTimeStr(hit.off_min) : '22:00',
          enabled: hit && hit.enabled ? 1 : 0,
        }
      })
      return
    }
    scheduleKind.value = 'together'
    togetherSlots.value = list.map((r) => ({
      days: maskToDaysArr(parseInt(r.dow_mask, 10) || 0),
      onStr: minToTimeStr(r.on_min),
      offStr: minToTimeStr(r.off_min),
      enabled: r.enabled ? 1 : 0,
    }))
  }

  function mapCycleRules(list) {
    if (!list.length) {
      cycleSlots.value = [defaultCycleSlot()]
      enableCycle.value = false
      return
    }
    enableCycle.value = true
    cycleSlots.value = list.map((r) => {
      const on = parseInt(r.on_sec, 10) || 0
      const off = parseInt(r.off_sec, 10) || 0
      const onMin = parseInt(r.on_min, 10) || 0
      const offMin = parseInt(r.off_min, 10) || 0
      const hasWin = onMin !== 0 || offMin !== 0
      return {
        days: maskToDaysArr(parseInt(r.dow_mask, 10) || 0),
        onM: Math.floor(on / 60),
        onS: on % 60,
        offM: Math.floor(off / 60),
        offS: off % 60,
        useWinLimit: hasWin,
        winOnStr: hasWin ? minToTimeStr(onMin) : '09:00',
        winOffStr: hasWin ? minToTimeStr(offMin) : '17:00',
        enabled: r.enabled ? 1 : 0,
      }
    })
  }

  function applyLoadedRules(list) {
    err.value = ''
    const win = list.filter((r) => (r.rule_kind || 'window') === 'window')
    const cyc = list.filter((r) => r.rule_kind === 'cycle')
    mapWindowRules(win)
    mapCycleRules(cyc)
    if (!win.length && !cyc.length) {
      enableWindow.value = true
      enableCycle.value = false
    }
  }

  function buildWindowRules() {
    if (!enableWindow.value) return []
    if (scheduleKind.value === 'eachDay') {
      const out = []
      let si = 0
      eachDayRows.value.forEach((row) => {
        if (!row.enabled) return
        out.push({
          rule_kind: 'window',
          dow_mask: row.bit,
          slot_index: si++,
          on_min: timeStrToMin(row.onStr),
          off_min: timeStrToMin(row.offStr),
          enabled: 1,
        })
      })
      return out
    }
    const out = []
    let si = 0
    togetherSlots.value.forEach((s) => {
      if (!s.enabled) return
      const mask = daysArrToMask(s.days)
      if (mask === 0) throw new Error('시간대: 요일을 하나 이상 선택하세요.')
      out.push({
        rule_kind: 'window',
        dow_mask: mask,
        slot_index: si++,
        on_min: timeStrToMin(s.onStr),
        off_min: timeStrToMin(s.offStr),
        enabled: 1,
      })
    })
    return out
  }

  function buildCycleRules(slotStart) {
    if (!enableCycle.value) return []
    const out = []
    let si = slotStart
    cycleSlots.value.forEach((c) => {
      if (!c.enabled) return
      const mask = daysArrToMask(c.days)
      if (mask === 0) throw new Error('주기: 요일을 하나 이상 선택하세요.')
      const onT = partsToSec(c.onM, c.onS)
      const offT = partsToSec(c.offM, c.offS)
      if (onT + offT === 0) throw new Error('주기: ON·OFF 길이 합이 0일 수 없습니다.')
      let onMin = 0
      let offMin = 0
      if (c.useWinLimit) {
        onMin = timeStrToMin(c.winOnStr)
        offMin = timeStrToMin(c.winOffStr)
        if (onMin === offMin) {
          throw new Error('주기 시간대: 켜짐·꺼짐 시각이 같을 수 없습니다.')
        }
      }
      out.push({
        rule_kind: 'cycle',
        dow_mask: mask,
        slot_index: si++,
        on_min: onMin,
        off_min: offMin,
        on_sec: onT,
        off_sec: offT,
        enabled: 1,
      })
    })
    return out
  }

  function buildPayloadRules() {
    const win = buildWindowRules()
    const cyc = buildCycleRules(win.length)
    const out = [...win, ...cyc]
    if (!out.length) {
      throw new Error('시간대 또는 주기 규칙을 하나 이상 켜고 저장하세요.')
    }
    return out
  }

  async function loadSch() {
    loading.value = true
    err.value = ''
    msg.value = ''
    try {
      const dev = getDeviceId()
      const ch = getChannel()
      const j = await apiJson(
        `/api/schedule?device_id=${encodeURIComponent(dev)}&channel=${encodeURIComponent(ch)}`,
      )
      applyLoadedRules(j.rules || [])
      msg.value = '불러옴'
    } catch (e) {
      err.value = e.message || String(e)
    } finally {
      loading.value = false
    }
  }

  async function saveSch() {
    loading.value = true
    err.value = ''
    msg.value = ''
    try {
      const rules = buildPayloadRules()
      const dev = getDeviceId()
      const ch = getChannel()
      const j = await apiJson(
        `/api/schedule?device_id=${encodeURIComponent(dev)}&channel=${encodeURIComponent(ch)}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json; charset=utf-8' },
          body: JSON.stringify({ rules }),
        },
      )
      if (j.error) throw new Error(j.error)
      const mqtt = j.mqtt === 'published' ? 'MQTT 전송됨' : `MQTT: ${j.mqtt || '?'}`
      msg.value = `저장됨 (${rules.length}건) · ${mqtt}`
    } catch (e) {
      err.value = e.message || String(e)
    } finally {
      loading.value = false
    }
  }

  return {
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
  }
}
