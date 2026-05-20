# -*- coding: utf-8 -*-
"""설정 오른쪽 카드: 채널 전체 24h 스케줄 미리보기."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "nodered/dashboard/cronusfarm_d1_settings_tools.html"

CSS = """
    .cf-sch-overview{margin-bottom:14px;padding:12px 14px;border-radius:16px;border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.04)}
    .cf-sch-overview-hd{font-size:16px;font-weight:900;color:#ffb830;margin:0 0 8px}
    .cf-sch-overview-sub{font-size:11px;font-weight:600;color:#9db0cc}
    .cf-sch-overview-bar{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end;margin-bottom:10px}
    .cf-sch-overview-list{display:flex;flex-direction:column;gap:4px;max-height:min(70vh,520px);overflow-y:auto}
    .cf-sch-overview-row{display:grid;grid-template-columns:92px 1fr;gap:8px;align-items:center;padding:3px 6px;border-radius:8px;cursor:pointer}
    .cf-sch-overview-row:hover{background:rgba(45,255,122,.08)}
    .cf-sch-overview-lbl{font-size:11px;font-weight:800;color:#c8e6c9;word-break:break-all}
    .cf-sch-overview-row canvas{width:100%;height:34px;display:block;border-radius:6px;background:rgba(0,0,0,.35)}
    .cf-sch-overview-foot{font-size:10px;color:#7a8bad;margin:8px 0 0;line-height:1.4}
"""

OVERVIEW_HTML = """
  <div id="mount-sch-overview"></div>
  <hr style="border:none;border-top:1px solid rgba(255,255,255,.1);margin:16px 0"/>
"""

OVERVIEW_JS = r"""
function cfTimeStrToMin(s) {
  const p = (s || '00:00').split(':');
  let hh = parseInt(p[0], 10), mm = parseInt(p[1], 10);
  if (isNaN(hh)) hh = 0;
  if (isNaN(mm)) mm = 0;
  return Math.min(1439, hh * 60 + mm);
}
function cfDrawSch24h(canvas, rules) {
  if (!canvas || !canvas.getContext) return;
  const ctx = canvas.getContext('2d');
  const padL = 28, padR = 4, padT = 4, padB = 12;
  const W = canvas.width, H = canvas.height;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = 'rgba(0,0,0,.35)';
  ctx.fillRect(padL, padT, plotW, plotH);
  ctx.strokeStyle = 'rgba(45,255,122,.15)';
  ctx.fillStyle = '#6b9c73';
  ctx.font = '9px system-ui,sans-serif';
  const drawSeg = (onMin, offMin, color) => {
    const x1 = padL + (onMin / 1440) * plotW;
    const x2 = padL + (offMin / 1440) * plotW;
    const w = Math.max(1, x2 - x1);
    ctx.fillStyle = color + '55';
    ctx.fillRect(x1, padT + 2, w, plotH - 4);
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.strokeRect(x1, padT + 2, w, plotH - 4);
  };
  for (let h = 0; h <= 24; h += 12) {
    const x = padL + (h / 24) * plotW;
    ctx.beginPath();
    ctx.moveTo(x, padT);
    ctx.lineTo(x, padT + plotH);
    ctx.stroke();
    if (h === 0 || h === 24) ctx.fillText(String(h).padStart(2, '0'), x, H - 2);
  }
  const colors = ['#2dff7a', '#4fc3f7', '#ffb830'];
  const list = rules || [];
  const cyc = list.filter(r => r.rule_kind === 'cycle');
  const win = list.filter(r => (r.rule_kind || 'window') === 'window');
  if (cyc.length) {
    const r = cyc.find(x => x.enabled) || cyc[0];
    const onSec = parseInt(r.on_sec, 10) || 0, offSec = parseInt(r.off_sec, 10) || 0;
    const period = onSec + offSec;
    if (period) {
      let t = 0, on = true;
      while (t < 86400) {
        const dur = on ? onSec : offSec;
        const end = Math.min(86400, t + dur);
        if (on) drawSeg(t / 60, end / 60, colors[0]);
        t = end;
        on = !on;
      }
    }
    return;
  }
  let idx = 0;
  for (const r of win) {
    if (!r.enabled) continue;
    const on = parseInt(r.on_min, 10) || 0;
    const off = parseInt(r.off_min, 10) || 0;
    const color = colors[idx % colors.length];
    idx += 1;
    if (off > on) drawSeg(on, off, color);
    else {
      drawSeg(on, 1440, color);
      if (off > 0) drawSeg(0, off, color);
    }
  }
}
const CF_SCH_CHANNELS = ['led_a1','led_a2','pump_a1','pump_a2','led_b1','led_b2','pump_b1','pump_b2','fan_a1','fan_a2','fan_b1','fan_b2','pump_c1','pump_c2','pump_d1','pump_d2'];
const SchOverviewApp = {
  data() {
    return {
      apiBase: '/farm/cronusfarm-sqlite',
      deviceId: 'cronusfarm-01',
      rows: CF_SCH_CHANNELS.map(k => ({ key: k, rules: [] })),
      loading: false,
    };
  },
  mounted() {
    try {
      const s = localStorage.getItem('cfDeviceId');
      if (s && s.trim()) this.deviceId = s.trim();
    } catch (e) {}
    this.loadAll();
    this._devTimer = setInterval(() => this.syncDev(), 5000);
  },
  unmounted() {
    if (this._devTimer) clearInterval(this._devTimer);
  },
  methods: {
    syncDev() {
      try {
        const s = localStorage.getItem('cfDeviceId');
        if (s && s.trim() && s.trim() !== this.deviceId) {
          this.deviceId = s.trim();
          this.loadAll();
        }
      } catch (e) {}
    },
    pickChannel(ch) {
      window.dispatchEvent(new CustomEvent('cf-sch-goto', { detail: { channel: ch } }));
    },
    async loadAll() {
      this.loading = true;
      const o = window.location.origin || '';
      await Promise.all(this.rows.map(async row => {
        try {
          const u = o + this.apiBase + '/api/schedule?device_id=' + encodeURIComponent(this.deviceId) + '&channel=' + encodeURIComponent(row.key);
          const r = await fetch(u, { credentials: 'same-origin' });
          row.rules = r.ok ? ((await r.json()).rules || []) : [];
        } catch (e) {
          row.rules = [];
        }
      }));
      this.loading = false;
      this.$nextTick(() => {
        this.rows.forEach(row => {
          const ref = this.$refs['cv_' + row.key];
          const canvas = Array.isArray(ref) ? ref[0] : ref;
          if (canvas) cfDrawSch24h(canvas, row.rules);
        });
        cfIframeResizeNotify();
      });
    },
  },
  template: `<div class="cf-sch-overview">
    <h2 class="cf-sch-overview-hd">채널별 스케줄 <span class="cf-sch-overview-sub">(0:00–24:00 · 전체)</span></h2>
    <div class="cf-sch-overview-bar">
      <label class="cf2-sch-lab">장치 ID <input v-model="deviceId" class="cf2-sch-inp" type="text" style="min-width:160px" @change="loadAll"/></label>
      <button type="button" class="cf2-sch-btn" :disabled="loading" @click="loadAll">새로고침</button>
    </div>
    <div class="cf-sch-overview-list">
      <div v-for="row in rows" :key="row.key" class="cf-sch-overview-row" @click="pickChannel(row.key)">
        <span class="cf-sch-overview-lbl">{{ row.key }}</span>
        <canvas :ref="'cv_' + row.key" width="720" height="34"></canvas>
      </div>
    </div>
    <p class="cf-sch-overview-foot">행 클릭 → 아래 편집 영역에서 해당 채널 선택 · 색 막대=켜짐 구간</p>
  </div>`,
};
"""


def patch() -> None:
    txt = TOOLS.read_text(encoding="utf-8")
    if "mount-sch-overview" in txt:
        print("skip: already patched")
        return
    if ".cf-sch-overview{" not in txt:
        txt = txt.replace("  </style>\n</head>", CSS + "\n  </style>\n</head>", 1)
    txt = txt.replace(
        '  <script type="text/x-template" id="tpl-schedule">',
        OVERVIEW_HTML
        + '  <script type="text/x-template" id="tpl-schedule">',
        1,
    )
    if '채널별 스케줄 편집' not in txt:
        txt = txt.replace(
            '<div class="cf2-sch-hd">스케줄 변경하기</div>',
            '<div class="cf2-sch-hd">채널별 스케줄 편집</div>',
            1,
        )
    insert_at = "ScheduleApp.template = '#tpl-schedule';"
    js = OVERVIEW_JS.replace("<motion", "<div").replace("</motion>", "</div>")
    block = (
        js
        + "\nVue.createApp(SchOverviewApp).mount('#mount-sch-overview');\n"
        + "window.addEventListener('cf-sch-goto', function(ev) {\n"
        + "  var ch = ev.detail && ev.detail.channel;\n"
        + "  if (!ch || !window.__cfScheduleVm) return;\n"
        + "  window.__cfScheduleVm.channel = ch;\n"
        + "  window.__cfScheduleVm.loadSch();\n"
        + "  try { document.getElementById('cf-sch-device-id').value = window.__cfScheduleVm.deviceId; } catch(e){}\n"
        + "});\n"
    )
    txt = txt.replace(
        insert_at,
        block + insert_at,
        1,
    )
    txt = txt.replace(
        "Vue.createApp(ScheduleApp).mount('#mount-schedule');",
        "window.__cfScheduleVm = Vue.createApp(ScheduleApp).mount('#mount-schedule');",
        1,
    )
    TOOLS.write_text(txt, encoding="utf-8")
    print("OK patch_settings_sch_overview")


if __name__ == "__main__":
    patch()
