<script setup>
import { Chart, registerables } from 'chart.js'
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useChartClock } from '@/composables/useChartClock'
import {
  cfDayWindowMs,
  mergeTeleLiveTail,
  nowMarkerMs,
  scheduleOnSegments,
  shouldShowNowMarker,
  teleOnSegments,
} from '@/lib/scheduleCanvas'

Chart.register(...registerables)

function drawMsSegments(ctx, xs, area, segments, fillStyle, strokeStyle) {
  if (!segments?.length || !xs || !area) return
  const top = area.top + 1
  const h = Math.max(1, area.bottom - area.top - 2)
  for (const { t0, t1 } of segments) {
    const x1 = xs.getPixelForValue(t0)
    const x2 = xs.getPixelForValue(t1)
    if (!Number.isFinite(x1) || !Number.isFinite(x2)) continue
    const left = Math.min(x1, x2)
    const w = Math.max(1, Math.abs(x2 - x1))
    ctx.fillStyle = fillStyle
    ctx.fillRect(left, top, w, h)
    if (strokeStyle) {
      ctx.strokeStyle = strokeStyle
      ctx.lineWidth = 1
      ctx.strokeRect(left, top, w, h)
    }
  }
}

const cronusFarmSchChartPlugin = {
  id: 'cronusFarmSchChart',
  afterDatasetsDraw(chart) {
    const w = chart.$cfWin
    const xs = chart.scales.x
    const area = chart.chartArea
    if (!w || !xs || !area) return
    const { ctx } = chart

    drawMsSegments(
      ctx,
      xs,
      area,
      chart.$cfPlanSegs,
      'rgba(45,255,122,0.38)',
      '#2dff7a',
    )
    /* tele(실측) — plan 위에 그려 겹침에서도 노란색이 보이게 */
    drawMsSegments(ctx, xs, area, chart.$cfTeleSegs, 'rgba(255,214,10,0.08)', 'rgba(255,214,10,0.28)')
  },
  afterDraw(chart) {
    const w = chart.$cfWin
    const xs = chart.scales.x
    const area = chart.chartArea
    if (!w?.showNow || !xs || !area) return
    const xNow = xs.getPixelForValue(w.nowMs)
    const xEnd = xs.getPixelForValue(w.tEnd)
    if (!Number.isFinite(xNow) || !Number.isFinite(xEnd)) return
    const left = area.left
    const right = area.right
    const xClip = Math.max(left, Math.min(right, xNow))
    const xRight = Math.max(left, Math.min(right, xEnd))
    const { ctx } = chart
    ctx.save()
    if (xRight > xClip + 0.5) {
      ctx.fillStyle = 'rgba(0,0,0,0.5)'
      ctx.fillRect(xClip, area.top, xRight - xClip, area.bottom - area.top)
    }
    ctx.strokeStyle = '#ff2d2d'
    ctx.lineWidth = 2.5
    ctx.setLineDash([])
    ctx.beginPath()
    ctx.moveTo(xClip + 0.5, area.top)
    ctx.lineTo(xClip + 0.5, area.bottom)
    ctx.stroke()
    ctx.restore()
  },
}
if (!Chart.registry.plugins.get('cronusFarmSchChart')) {
  Chart.register(cronusFarmSchChartPlugin)
}

const props = defineProps({
  rules: { type: Array, default: () => [] },
  execData: { type: Object, default: null },
  dayWindow: { type: Object, default: null },
  showTimeAxis: { type: Boolean, default: true },
})

const { chartNowMs, piDayWindow } = useChartClock()

const wrapRef = ref(null)
const canvasRef = ref(null)
let chart = null
let resizeObs = null
let tickTimer = null

const CHART_PAD_COMPACT = { top: 1, right: 2, bottom: 0, left: 2 }
const CHART_PAD_AXIS = { top: 1, right: 2, bottom: 2, left: 2 }

function makeXTickCallback(tStart, tEnd) {
  const fmt = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Seoul',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
  return (v) => {
    if (v == null || !Number.isFinite(v)) return ''
    const n = Number(v)
    if (Math.abs(n - tEnd) < 90_000) return '24:00'
    if (Math.abs(n - tStart) < 90_000) return '00:00'
    const parts = fmt.formatToParts(new Date(n))
    const h = parts.find((p) => p.type === 'hour')?.value || '00'
    const m = parts.find((p) => p.type === 'minute')?.value || '00'
    return `${h}:${m}`
  }
}

function chartOptions(tStart, tEnd, showTimeAxis) {
  const span = tEnd - tStart
  const step = span > 0 ? span / 6 : 4 * 3600 * 1000
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    clip: true,
    interaction: { mode: 'index', intersect: false },
    layout: { padding: showTimeAxis ? CHART_PAD_AXIS : CHART_PAD_COMPACT },
    scales: {
      x: {
        type: 'linear',
        min: tStart,
        max: tEnd,
        grid: { color: 'rgba(45,255,122,0.1)' },
        ticks: {
          display: showTimeAxis,
          stepSize: step,
          autoSkip: false,
          maxRotation: 0,
          padding: 0,
          color: '#9fb0c4',
          font: { size: 7, weight: '500' },
          callback: makeXTickCallback(tStart, tEnd),
        },
      },
      y: {
        display: false,
        min: 0,
        max: 1,
      },
    },
    plugins: {
      legend: { display: false },
      tooltip: { enabled: false },
    },
  }
}

function render() {
  const canvas = canvasRef.value
  if (!canvas) return

  const nowMs = chartNowMs()
  const dayWin = props.dayWindow || piDayWindow()
  const { tStart, tEnd } = cfDayWindowMs(props.execData, dayWin, nowMs)
  const nowLineMs = nowMarkerMs(tStart, tEnd, nowMs)
  const showNow = shouldShowNowMarker(tStart, tEnd, nowMs)
  const planSegs = scheduleOnSegments(props.rules, tStart, tEnd)
  const telePts = mergeTeleLiveTail(props.execData, tEnd, nowMs)
  const teleSegs = teleOnSegments(telePts, tStart, tEnd, nowMs)

  const datasets = [
    {
      label: '_axis',
      data: [
        { x: tStart, y: 0 },
        { x: tEnd, y: 0 },
      ],
      borderWidth: 0,
      pointRadius: 0,
      fill: false,
    },
  ]

  const options = chartOptions(tStart, tEnd, props.showTimeAxis)
  const cfWin = {
    tStart,
    tEnd,
    nowMs: nowLineMs ?? nowMs,
    showNow: showNow && nowLineMs != null,
  }
  if (!chart) {
    chart = new Chart(canvas, { type: 'line', data: { datasets }, options })
  } else {
    chart.data.datasets = datasets
    chart.options = options
  }
  chart.$cfWin = cfWin
  chart.$cfPlanSegs = planSegs
  chart.$cfTeleSegs = teleSegs
  chart.update('none')
}

function destroyChart() {
  chart?.destroy()
  chart = null
}

onMounted(() => {
  render()
  tickTimer = setInterval(() => render(), 5000)
  if (typeof ResizeObserver !== 'undefined' && wrapRef.value) {
    resizeObs = new ResizeObserver(() => {
      chart?.resize()
      chart?.draw()
    })
    resizeObs.observe(wrapRef.value)
  }
})

onUnmounted(() => {
  if (tickTimer) clearInterval(tickTimer)
  resizeObs?.disconnect()
  destroyChart()
})

watch(
  () => [props.rules, props.execData, props.showTimeAxis],
  () => render(),
  { deep: true },
)
</script>

<template>
  <div ref="wrapRef" class="cf-sch-chart-wrap">
    <canvas ref="canvasRef" />
  </div>
</template>
