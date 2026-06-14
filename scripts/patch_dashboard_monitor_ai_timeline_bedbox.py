# -*- coding: utf-8 -*-
"""모니터: AI 카메라 /farm/ai-mjpeg, Bed A~D 타임라인(스택). 그래프는 GET /farm/cronusfarm-sqlite/api/channel/timeline → tele_channel_fact."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
NGINX = ROOT / "deploy" / "nginx" / "cronusfarm-nodered.conf"

REMOVE_IDS = {
    "ui_tpl_hist_combo_a",
    "ui_tpl_hist_led_a1",
    "ui_tpl_hist_led_a2",
    "ui_tpl_hist_pump_a1",
    "ui_tpl_hist_pump_a2",
    "ui_tpl_hist_fan_a1",
    "ui_tpl_hist_fan_a2",
    "ui_tpl_hist_combo_b",
    "ui_tpl_hist_led_b1",
    "ui_tpl_hist_pump_b1",
    "ui_tpl_hist_pump_b2",
    "ui_tpl_hist_fan_b1",
    "ui_tpl_hist_fan_b2",
}

# 기존 ui_tpl_css_cronus 안의 Bed 타임라인 블록을 최신으로 덮어씀(여백·캔버스 높이 갱신)
RE_BED_HIST_CSS_BLOCK = re.compile(
    r"/\* Bed 타임라인[\s\S]*?(?:\.cf-bed-hist-cwrap canvas|\.cf-bed-hist-row canvas)\{[^}]*\}\s*",
    re.MULTILINE,
)

BED_HIST_CSS = """
/* Bed 타임라인: 행 간격 최소, 장치명은 그래프+시간축 블록 세로 중앙 */
.cf-bed-hist-box{font-family:system-ui,sans-serif;padding:0;margin:0;}
.nr-dashboard-theme .nr-dashboard-group:has(.cf-bed-hist-box) .nr-dashboard-template,
body.nr-dashboard-theme md-card:has(.cf-bed-hist-box) .nr-dashboard-template{
  height:auto!important;min-height:0!important;max-height:none!important;}
.cf-bed-hist-hd{font-size:12px;color:#9db0cc;margin:0 0 2px;font-weight:800;}
.cf-bed-hist-stack{display:flex;flex-direction:column;gap:0;margin:0;padding:0;}
.cf-bed-hist-row{display:grid;grid-template-columns:56px minmax(0,1fr);gap:2px;align-items:center;margin:0;padding:0;}
.cf-bed-hist-stack>.cf-bed-hist-row+.cf-bed-hist-row{margin-top:-4px;}
.cf-bed-hist-row span{font-size:11px;color:#e6edf7;font-weight:700;padding:0 4px 0 0;display:inline-block;max-width:100%;line-height:1.2;text-align:right;align-self:center;}
.cf-bed-hist-cwrap{min-height:0;overflow:visible;padding:0;margin:0;display:block;width:100%;}
.cf-bed-hist-cwrap canvas{width:100%!important;height:62px!important;max-height:none!important;display:block;}
"""

SCHED_DEF_CSS = """
/* 기본 스케줄표 — Bed별 카드(타일) */
.cf-sched-def-box{font-family:system-ui,sans-serif;padding:0 4px 6px;margin:0;}
.nr-dashboard-theme .nr-dashboard-group:has(.cf-sched-def-box) .nr-dashboard-template,
body.nr-dashboard-theme md-card:has(.cf-sched-def-box) .nr-dashboard-template{
  height:auto!important;min-height:0!important;max-height:none!important;}
.cf-sched-def-hd{font-size:13px;color:#aed581;margin:0 0 2px;font-weight:800;}
.cf-sched-def-sub{font-size:11px;color:#9db0cc;margin:0 0 8px;}
.cf-sched-def-beds{display:flex;flex-direction:column;gap:10px;}
.cf-sched-def-bed-hd{font-size:12px;color:#8bc34a;font-weight:800;margin:0 0 6px;}
.cf-sched-def-tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(148px,1fr));gap:6px;}
.cf-sched-def-tile{background:rgba(30,40,55,.72);border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:8px 9px;min-height:64px;}
.cf-sched-def-tile-ch{font-size:11px;font-weight:800;color:#e6edf7;margin:0 0 4px;}
.cf-sched-def-tile-kind{display:inline-block;font-size:10px;font-weight:700;color:#ffcc80;background:rgba(255,204,128,.12);padding:2px 6px;border-radius:6px;margin:0 0 5px;}
.cf-sched-def-tile-detail{font-size:10px;color:#b8c5d9;line-height:1.35;}
"""

CSS_INJECT = """
/* AI 카메라: 영상 상하 중앙 + 자막은 아래(overflow 잘림 방지) */
.nr-dashboard-theme .cf-ai-cam-outer{
  position:relative;width:100%;max-width:100%;display:flex;flex-direction:column;align-items:center;box-sizing:border-box;}
.nr-dashboard-theme .cf-ai-cam-stage,
.nr-dashboard-theme .cf-ai-cam-root{
  position:relative;width:100%;flex:1 1 auto;
  min-height:min(44vh,360px);max-height:min(62vh,520px);
  display:flex;align-items:center;justify-content:center;
  background:#050a12;overflow:hidden;text-align:center;box-sizing:border-box;}
.nr-dashboard-theme .cf-ai-cam-stage img,
.nr-dashboard-theme .cf-ai-cam-root img{
  width:auto;max-width:100%;height:auto;max-height:min(58vh,500px);
  object-fit:contain;object-position:center center;
  display:block;margin:0 auto;background:#000;cursor:pointer;flex:0 0 auto;}
.nr-dashboard-theme .cf-ai-cam-caption{
  position:relative;flex:0 0 auto;width:100%;z-index:5;
  padding:10px 12px 6px;margin:0;
  font-size:13px;font-weight:800;color:#e8f5e9;text-align:center;line-height:1.45;
  pointer-events:none;text-shadow:0 1px 3px rgba(0,0,0,.9);
  background:rgba(5,10,18,.92);box-sizing:border-box;
  white-space:normal;word-break:keep-all;}
.nr-dashboard-theme .nr-dashboard-group:has(.cf-ai-cam-outer) .nr-dashboard-template,
body.nr-dashboard-theme md-card:has(.cf-ai-cam-outer) .nr-dashboard-template{overflow:visible!important;max-height:none!important;height:auto!important;min-height:0!important;}
body.nr-dashboard-theme md-card:has(.cf-ai-cam-outer),
.nr-dashboard-theme .nr-dashboard-group:has(.cf-ai-cam-outer) md-card{height:auto!important;min-height:0!important;overflow:visible!important;}
body.nr-dashboard-theme md-card:has(.cf-ai-cam-outer) md-card-content{padding-bottom:8px!important;height:auto!important;min-height:0!important;overflow:visible!important;}
""" + BED_HIST_CSS + SCHED_DEF_CSS

GH_GAUGE_MARK = "/* cf-gh-sensor-gauge-text v1 */"
GH_GAUGE_END = "/* end cf-gh-sensor */"
GH_GAUGE_TEXT_CSS = (
    "\n"
    + GH_GAUGE_MARK
    + "\n"
    + """.nr-dashboard-theme .cf-gh-data-dark .nr-dashboard-cardtitle,
.nr-dashboard-theme .cf-gh-data-dark .nr-dashboard-group .nr-dashboard-cardtitle,
.nr-dashboard-theme .cf-gh-data-dark md-card .md-toolbar-tools,
.nr-dashboard-theme .cf-gh-data-dark .nr-dashboard-cardpanel .md-title,
.nr-dashboard-theme .cf-gh-data-dark .nr-dashboard-cardpanel .md-subhead,
.nr-dashboard-theme .cf-gh-data-dark .nr-dashboard-cardpanel p,
.nr-dashboard-theme .cf-gh-data-dark md-card-content,
.nr-dashboard-theme .cf-gh-data-dark md-card-content .md-title,
.nr-dashboard-theme .cf-gh-data-dark .value,
.nr-dashboard-theme .cf-gh-data-dark .label{color:#e8f0ff!important;}
.nr-dashboard-theme .cf-gh-data-dark .nr-dashboard-cardpanel .md-subhead{color:#c5d6ea!important;}
.nr-dashboard-theme .cf-gh-data-dark svg text{fill:#eaf1ff!important;}
"""
    + GH_GAUGE_END
    + "\n"
)

RE_GH_GAUGE_CSS_BLOCK = re.compile(
    re.escape(GH_GAUGE_MARK) + r"[\s\S]*?" + re.escape(GH_GAUGE_END) + r"\s*",
    re.MULTILINE,
)

# 모니터 탭 툴바 우측: 현재 날짜·시간 — CSS는 전역 템플릿, 스크립트는 AI 카메라(모니터 탭 order 1)에서 먼저 실행
CLOCK_INJECT_MARK = "/* cf-monitor-tab-clock */"
CLOCK_CSS_BLOCK = """
<style>
""" + CLOCK_INJECT_MARK + """
body.nr-dashboard-theme md-toolbar .md-toolbar-tools:has(#cf-monitor-tab-clock){
  display:flex!important;align-items:center!important;flex-wrap:wrap!important;gap:4px 8px;}
body.nr-dashboard-theme md-toolbar .md-toolbar-tools:has(#cf-monitor-tab-clock) md-tabs{
  flex:1 1 auto;min-width:0;}
#cf-monitor-tab-clock{
  margin-left:auto;flex-shrink:0;font-size:13px;font-weight:800;color:var(--cf-title,#FFD54F);
  white-space:nowrap;padding:0 4px 0 10px;font-variant-numeric:tabular-nums;line-height:1.2;}
</style>
"""

# 예전: 시계 스크립트가 ui_tpl_css_cronus(그룹 order 8)에만 있어 늦게 실행될 수 있음 → css에서 제거 후 AI 템플릿으로 이전
RE_LEGACY_CLOCK_SCRIPT = re.compile(
    r"<script\s+type=\"text/javascript\">\s*\(function\(\)\{\s*var\s+ID=[\"']cf-monitor-tab-clock[\"'][\s\S]*?</script>\s*",
)

# 구 패치로 </style> 직후에 AI 카메라 보조 CSS가 한 번 더 붙어(스타일 태그 밖) /ui 전체가 안 뜨는 경우가 있음 → 제거
RE_ORPHAN_AI_CSS_AFTER_STYLE = re.compile(
    r"(</style>)\s*/\* AI 카메라 캡션: 부모 overflow로 잘리지 않게 \*/\s*"
    r"\.nr-dashboard-theme \.nr-dashboard-group:has\(\.cf-ai-cam-outer\)[\s\S]*?\}\s*(?=<style>)",
)


def _repair_ui_tpl_css_cronus_format(fmt: str) -> str:
    fmt = RE_LEGACY_CLOCK_SCRIPT.sub("", fmt)
    fmt = RE_ORPHAN_AI_CSS_AFTER_STYLE.sub(r"\1\n\n", fmt, count=1)
    return fmt


def _inject_or_refresh_gh_gauge_css(fmt: str) -> str:
    """센서 Data 그룹(.cf-gh-data-dark) 게이지·차트 글자색 — 블록 갱신 또는 </style> 앞 삽입."""
    core = GH_GAUGE_TEXT_CSS.strip() + "\n"
    if GH_GAUGE_MARK in fmt:
        return RE_GH_GAUGE_CSS_BLOCK.sub(core, fmt, count=1)
    idx = fmt.rfind("</style>")
    if idx >= 0:
        return fmt[:idx] + "\n" + core + fmt[idx:]
    return fmt + "\n<style>\n" + core + "</style>\n"


# 툴바 시계: V2 가드(구 __cfMonitorToolbarClock 세션 잔존 무시) + Pi API 시각 보정
MONITOR_CLOCK_BOOT = r"""<script type="text/javascript">
(function(){
  if(window.__cfMonitorToolbarClockV2)return; window.__cfMonitorToolbarClockV2=1;
  var ID="cf-monitor-tab-clock";
  var NEEDLE="CronusFarm";
  var CF_TZ="Asia/Seoul";
  var skewMs=0;
  function pad2(n){return String(n).padStart(2,"0");}
  function findToolbarTools(){
    var list=document.querySelectorAll("md-toolbar .md-toolbar-tools");
    for(var i=0;i<list.length;i++){
      var el=list[i];
      if(el.querySelector("md-tabs") && (el.textContent||"").indexOf(NEEDLE)>=0) return el;
    }
    return document.querySelector("md-toolbar .md-toolbar-tools");
  }
  function fmtKstNow(){
    var d=new Date(Date.now()+skewMs);
    try{
      var p={};
      new Intl.DateTimeFormat("en-GB",{timeZone:CF_TZ,hour12:false,year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",second:"2-digit"}).formatToParts(d).forEach(function(x){p[x.type]=x.value;});
      return p.year+"."+p.month+"."+p.day+" "+p.hour+":"+p.minute+":"+p.second+" KST";
    }catch(e){
      var t=d.getTime()+9*60*60*1000,u=new Date(t);
      return u.getUTCFullYear()+"."+pad2(u.getUTCMonth()+1)+"."+pad2(u.getUTCDate())+" "+pad2(u.getUTCHours())+":"+pad2(u.getUTCMinutes())+":"+pad2(u.getUTCSeconds())+" KST";
    }
  }
  function syncServer(){
    fetch("/farm/cronusfarm-sqlite/api/time/now",{credentials:"same-origin"})
      .then(function(r){return r.ok?r.json():null;})
      .then(function(j){if(j&&j.pi_ts_ms)skewMs=Number(j.pi_ts_ms)-Date.now();})
      .catch(function(){});
  }
  function tick(){
    var el=document.getElementById(ID);
    if(!el) return;
    el.textContent=fmtKstNow();
  }
  function mount(){
    var host=findToolbarTools();
    if(!host) return;
    var el=document.getElementById(ID);
    if(!el){
      el=document.createElement("span");
      el.id=ID;
      host.appendChild(el);
    }
    tick();
  }
  syncServer();
  setInterval(syncServer,60000);
  setInterval(tick,1000);
  setInterval(mount,2000);
  setTimeout(mount,0);
  setTimeout(mount,800);
})();
</script>
"""

def _load_ai_cam_fmt() -> str:
    import importlib.util

    p = ROOT / "scripts" / "patch_dashboard_ai_camera_mjpeg.py"
    spec = importlib.util.spec_from_file_location("cf_ai_cam_patch", p)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.FMT


AI_FMT = MONITOR_CLOCK_BOOT + _load_ai_cam_fmt()

# Bed 타임라인 카드 제목(스택 HTML)
_BED_HIST_TITLE = {"a": "A Bed", "b": "B Bed", "c": "C Bed", "d": "D Bed"}

# farm-ui scheduleDefaultsDisplay.js 와 동일 (builtin·DB 시드)
SCHEDULE_DEFAULTS_BEDS = [
  {
    "bed": "A Bed",
    "rows": [
      { "label": "LED A1", "rule": "시간대", "detail": "06:30 ~ 18:30 ON · 그 외 OFF" },
      { "label": "LED A2", "rule": "시간대", "detail": "06:30 ~ 18:30 ON · 그 외 OFF" },
      {
        "label": "Pump A1",
        "rule": "주기",
        "detail": "0시부터 15분 ON / 20분 OFF 반복 (하루 종일)",
      },
      {
        "label": "Pump A2",
        "rule": "주기",
        "detail": "09:00~17:00 → 10분 ON / 50분 OFF · 그 외 5분 ON / 55분 OFF",
      },
      { "label": "Fan A1", "rule": "시간대", "detail": "06:00 ~ 24:00 ON · 그 외 OFF" },
      { "label": "Fan A2", "rule": "시간대", "detail": "06:00 ~ 24:00 ON · 그 외 OFF" },
    ],
  },
  {
    "bed": "B Bed",
    "rows": [
      { "label": "LED B1", "rule": "시간대", "detail": "07:30 ~ 17:30 ON · 그 외 OFF" },
      { "label": "LED B2", "rule": "시간대", "detail": "07:30 ~ 17:30 ON · 그 외 OFF" },
      {
        "label": "Pump B1",
        "rule": "주기",
        "detail": "07:30~17:30 → 3분 ON / 7분 OFF · 그 외 1분 ON / 9분 OFF",
      },
      {
        "label": "Pump B2",
        "rule": "주기",
        "detail": "09:00~17:00 → 10분 ON / 50분 OFF · 그 외 5분 ON / 55분 OFF",
      },
      { "label": "Fan B1", "rule": "시간대", "detail": "06:00 ~ 24:00 ON · 그 외 OFF" },
      { "label": "Fan B2", "rule": "시간대", "detail": "06:00 ~ 24:00 ON · 그 외 OFF" },
    ],
  },
  {
    "bed": "C Bed",
    "rows": [
      { "label": "Pump C1", "rule": "주기", "detail": "1시간 주기 · 1분 ON" },
      { "label": "Pump C2", "rule": "주기", "detail": "2시간 주기 · 1분 ON" },
    ],
  },
  {
    "bed": "D Bed",
    "rows": [
      { "label": "Pump D1", "rule": "주기", "detail": "3시간 주기 · 1분 ON" },
      { "label": "Pump D2", "rule": "주기", "detail": "4시간 주기 · 1분 ON" },
    ],
  },
]


# 실제 동작(tele) 타임라인 ON 구간 채움 — 선색 동일·연한 투명(24h 차트 tele 범례 0.09와 맞춤)
HIST_FILL_ALPHA = 0.12


def _fill_rgba(hex_color: str, alpha: float = HIST_FILL_ALPHA) -> str:
    """ON 구간 채우기용 — 선색과 동일 톤의 반투명 배경."""
    h = (hex_color or "").strip().lstrip("#")
    if len(h) != 6 or not all(c in "0123456789abcdefABCDEF" for c in h):
        return f"rgba(127,127,127,{alpha})"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _fmt_sched_defaults_cards() -> str:
    """모니터 탭: 기본 스케줄표 카드(타일) 그리드."""
    beds_html = []
    for bed in SCHEDULE_DEFAULTS_BEDS:
        tiles = []
        for row in bed["rows"]:
            tiles.append(
                f'<div class="cf-sched-def-tile">'
                f'<div class="cf-sched-def-tile-ch">{row["label"]}</div>'
                f'<span class="cf-sched-def-tile-kind">{row["rule"]}</span>'
                f'<div class="cf-sched-def-tile-detail">{row["detail"]}</div>'
                f"</div>"
            )
        beds_html.append(
            f'<section class="cf-sched-def-bed">'
            f'<div class="cf-sched-def-bed-hd">{bed["bed"]}</div>'
            f'<div class="cf-sched-def-tiles">{"".join(tiles)}</div>'
            f"</section>"
        )
    return (
        '<div class="cf-sched-def-box">'
        '<div class="cf-sched-def-hd">기본 스케줄표</div>'
        '<p class="cf-sched-def-sub">Bed 순 · DB 시드·펌웨어 builtin 동일 (테스트 중 pump D는 DB 값과 다를 수 있음)</p>'
        f'<div class="cf-sched-def-beds">{"".join(beds_html)}</div>'
        "</div>"
    )


def _sched_defaults_grid_height() -> int:
    n = sum(len(b["rows"]) for b in SCHEDULE_DEFAULTS_BEDS)
    return max(6, min(14, 3 + (n + 3) // 4))


def _remove_sched_defaults_monitor(flows: list) -> int:
    """모니터 탭 기본 스케줄 카드(타일) 제거 — 설정 SPA 「채널별 스케줄 편집」에만 표."""
    drop = {"ui_grp_sched_defaults", "ui_tpl_sched_defaults_monitor"}
    before = len(flows)
    flows[:] = [n for n in flows if n.get("id") not in drop]
    return before - len(flows)


def _nr_bed_hist_height(num_channels: int) -> int:
    """Node-RED Dashboard ui_template height(그리드 단): 제목 1 + 채널당 1, 하단 빈칸 최소화."""
    return max(3, 1 + int(num_channels))


def _colors_for_channels(channels: list[str]) -> list[str]:
    """채널 종류별 색 — farm-ui channelIcons(LED/Pump/Fan)와 동일."""
    out: list[str] = []
    for ch in channels:
        if ch.startswith("led"):
            out.append("#FFD54F")
        elif ch.startswith("pump"):
            out.append("#4FC3F7")
        elif ch.startswith("fan"):
            out.append("#43A047")
        else:
            out.append("#9fb0c4")
    return out


def _fmt_stack(bed: str, channels: list[str], labels: list[str], colors: list[str]) -> str:
    rows = []
    for ch, lb in zip(channels, labels):
        cid = f"cf_hc_{bed}_{ch}"
        rows.append(
            f'<div class="cf-bed-hist-row"><span>{lb}</span><div class="cf-bed-hist-cwrap">'
            f'<canvas id="{cid}" height="62" style="max-width:100%;height:62px;display:block"></canvas></div></div>'
        )
    rows_html = "\n    ".join(rows)
    ch_json = json.dumps(channels, ensure_ascii=False)
    lb_json = json.dumps(labels, ensure_ascii=False)
    col_json = json.dumps(colors, ensure_ascii=False)
    fills_json = json.dumps([_fill_rgba(c, 0.38) for c in colors], ensure_ascii=False)
    title = _BED_HIST_TITLE.get(bed, bed.upper() + " Bed")
    return f"""<div class="cf-bed-hist-box">
  <div class="cf-bed-hist-hd">{title} — 24h ON/OFF</div>
  <div class="cf-bed-hist-stack">
    {rows_html}
  </div>
</div>
<script src="/cronusfarm-static/cronusfarm_timeline_common.js"></script>
<script src="/cronusfarm-static/vendor/chart.umd.min.js"></script>
<script type="text/javascript">
(function(scope) {{
  const BED = {json.dumps(bed)};
  const CHANNELS = {ch_json};
  const LABELS = {lb_json};
  const COLS = {col_json};
  const FILLS_DYN = {fills_json};
  const API_BATCH = (location.origin || '') + '/farm/cronusfarm-sqlite/api/channel/timeline/batch';
  const charts = [];
  /* Chart.js: Bed 위젯마다 중복 로드·150ms 폴링 방지 — 전역 1회 */
  function ensureChart(cb) {{
    if (typeof Chart !== 'undefined') {{ cb(); return; }}
    var g = window.__cfChartJsReady;
    if (!g) {{
      g = new Promise(function(resolve, reject) {{
        function ok() {{ resolve(); }}
        var s = document.querySelector('script[src*="chart.umd"]');
        if (!s) {{
          s = document.createElement('script');
          s.src = '/cronusfarm-static/vendor/chart.umd.min.js';
          s.onload = ok;
          s.onerror = function() {{
            var cdn = document.createElement('script');
            cdn.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js';
            cdn.onload = ok;
            cdn.onerror = function() {{ reject(new Error('chart.js load failed')); }};
            document.head.appendChild(cdn);
          }};
          document.head.appendChild(s);
          return;
        }}
        var n = 0;
        (function wait() {{
          if (typeof Chart !== 'undefined') {{ ok(); return; }}
          if (++n > 50) {{ reject(new Error('chart.js timeout')); return; }}
          setTimeout(wait, 40);
        }})();
      }});
      window.__cfChartJsReady = g;
    }}
    g.then(cb).catch(function(e) {{ console.warn(e); }});
  }}
  function deviceId() {{
    try {{ const s = localStorage.getItem('cfDeviceId'); if (s && s.trim()) return s.trim(); }} catch (e) {{}}
    return 'cronusfarm-01';
  }}
  function mapTime(j) {{
    if (window.CfTimeline && CfTimeline.mapRolling24h) return CfTimeline.mapRolling24h(j);
    const tEnd = Date.now();
    return {{ tStart: tEnd - 24 * 3600 * 1000, tEnd: tEnd, nowMs: tEnd }};
  }}
  function renderOne(i, j) {{
    const ch = CHANNELS[i];
    const el = document.getElementById('cf_hc_' + BED + '_' + ch);
    if (!el) return;
    if (!j) j = {{ hours: 24, rolling: true, points: [], window_end_ms: Date.now() }};
    try {{
      const tt = mapTime(j);
      const x0 = Number(tt.tStart);
      const x1 = Number(tt.tEnd);
      const nowMs = Number(tt.nowMs || tt.tEnd);
      let pts = j.points || [];
      if (window.CfTimeline && CfTimeline.mergeTeleLiveTail) {{
        pts = CfTimeline.mergeTeleLiveTail(j, x1, nowMs);
      }}
      const data = pts.map(function(p) {{
        return {{ x: Number(p.ts_ms), y: (p.state === 1 || p.state === true) ? 1 : 0 }};
      }});
      data.sort(function(a, b) {{ return a.x - b.x; }});
      const xSpan = x1 - x0;
      const xTickStep = (xSpan > 0 && isFinite(xSpan)) ? (xSpan / 5) : (86400000 / 5);
      const opt = {{
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        clip: false,
        layout: {{ padding: {{ top: 0, right: 0, bottom: 11, left: 0 }} }},
        scales: {{
          x: {{
            type: 'linear',
            min: x0,
            max: x1,
            title: {{ display: false }},
            grid: {{ display: false }},
            ticks: {{
              display: true,
              stepSize: xTickStep,
              autoSkip: false,
              maxRotation: 0,
              color: '#9fb0c4',
              font: {{ size: 10, weight: '500' }},
              padding: 0,
              callback: function(v) {{
                if (v == null || !isFinite(v)) return '';
                var d = new Date(v);
                var h = d.getHours(), m = d.getMinutes();
                return (h < 10 ? '0' : '') + h + ':' + (m < 10 ? '0' : '') + m;
              }}
            }}
          }},
          y: {{
            position: 'right',
            min: -0.1,
            max: 1.1,
            grid: {{ display: false, drawBorder: false }},
            ticks: {{
              stepSize: 1,
              padding: 2,
              font: {{ size: 9 }},
              callback: function(v) {{ return v === 1 ? 'ON' : (v === 0 ? 'OFF' : ''); }}
            }}
          }}
        }},
        plugins: {{ legend: {{ display: false }} }}
      }};
      if (!charts[i]) {{
        charts[i] = new Chart(el.getContext('2d'), {{
          type: 'line',
          data: {{ datasets: [{{ label: LABELS[i], data: data, parsing: false, stepped: true, borderWidth: 1.5, borderColor: COLS[i], backgroundColor: FILLS_DYN[i], fill: true, pointRadius: 0 }}]}},
          options: opt
        }});
      }} else {{
        charts[i].data.datasets[0].data = data;
        charts[i].data.datasets[0].borderColor = COLS[i];
        charts[i].data.datasets[0].backgroundColor = FILLS_DYN[i];
        charts[i].options.scales.x.min = x0;
        charts[i].options.scales.x.max = x1;
        charts[i].options.scales.x.ticks.stepSize = xTickStep;
        charts[i].update();
      }}
    }} catch (e) {{ console.warn(e); }}
  }}
  async function loadAll() {{
    try {{
      const u = API_BATCH + '?device_id=' + encodeURIComponent(deviceId()) + '&channels=' + encodeURIComponent(CHANNELS.join(',')) + '&hours=24&rolling=1';
      const r = await fetch(u, {{ credentials: 'same-origin' }});
      if (!r.ok) {{ console.warn('timeline batch HTTP', r.status, BED); return; }}
      const batch = await r.json();
      const map = batch.channels || {{}};
      CHANNELS.forEach(function(ch, i) {{ renderOne(i, map[ch]); }});
    }} catch (e) {{ console.warn('timeline load', BED, e); }}
  }}
  function boot() {{ ensureChart(loadAll); }}
  boot();
  setInterval(boot, 60000);
  setTimeout(boot, 200);
  setTimeout(boot, 1200);
  if (scope && scope.$watch) {{
    scope.$watch('msg', function() {{ boot(); }});
  }}
}})(scope);
</script>"""


def patch_nginx() -> bool:
    txt = NGINX.read_text(encoding="utf-8")
    if "ai-mjpeg" in txt:
        return False
    needle = "  # CronusFarm http in (스케줄 API 프록시·telegram-ping 등) → 작업용 Node-RED\n  location ^~ /farm/ {"
    insert = """  # AI 카메라 MJPEG (8081) — /ui 와 동일 origin(HTTPS)에서 혼합 콘텐츠 회피
  location ^~ /farm/ai-mjpeg/ {
    proxy_pass http://127.0.0.1:8081/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_buffering off;
    proxy_read_timeout 86400s;
    proxy_send_timeout 86400s;
  }

"""
    if needle not in txt:
        raise SystemExit("nginx patch anchor not found")
    txt = txt.replace(needle, insert + needle, 1)
    NGINX.write_text(txt, encoding="utf-8")
    return True


def _apply_hist_nodes(flows: list, ch_a, lb_a, col_a, ch_b, lb_b, col_b, ch_c, lb_c, col_c, ch_d, lb_d, col_d) -> int:
    """ui_tpl_hist_stack_* format 갱신."""
    specs = {
        "ui_tpl_hist_stack_a": ("a", ch_a, lb_a, col_a),
        "ui_tpl_hist_stack_b": ("b", ch_b, lb_b, col_b),
        "ui_tpl_hist_stack_c": ("c", ch_c, lb_c, col_c),
        "ui_tpl_hist_stack_d": ("d", ch_d, lb_d, col_d),
    }
    n = 0
    for node in flows:
        nid = node.get("id")
        if nid not in specs:
            continue
        bed, ch, lb, col = specs[nid]
        ha = _nr_bed_hist_height(len(ch))
        node["format"] = _fmt_stack(bed, ch, lb, col)
        node["height"] = ha
        n += 1
    return n


def main() -> None:
    d = json.loads(DASH.read_text(encoding="utf-8-sig"))
    d = [n for n in d if n.get("id") not in REMOVE_IDS]

    ch_a = ["led_a1", "led_a2", "pump_a1", "pump_a2", "fan_a1", "fan_a2"]
    lb_a = ["LED A1", "LED A2", "Pump A1", "Pump A2", "Fan A1", "Fan A2"]
    col_a = _colors_for_channels(ch_a)

    ch_b = ["led_b1", "led_b2", "pump_b1", "pump_b2", "fan_b1", "fan_b2"]
    lb_b = ["LED B1", "LED B2", "Pump B1", "Pump B2", "Fan B1", "Fan B2"]
    col_b = _colors_for_channels(ch_b)

    ch_c = ["pump_c1", "pump_c2"]
    lb_c = ["Pump C1", "Pump C2"]
    col_c = _colors_for_channels(ch_c)

    ch_d = ["pump_d1", "pump_d2"]
    lb_d = ["Pump D1", "Pump D2"]
    col_d = _colors_for_channels(ch_d)

    ha, hb, hc, hd = (
        _nr_bed_hist_height(len(ch_a)),
        _nr_bed_hist_height(len(ch_b)),
        _nr_bed_hist_height(len(ch_c)),
        _nr_bed_hist_height(len(ch_d)),
    )

    new_a = {
        "id": "ui_tpl_hist_stack_a",
        "type": "ui_template",
        "z": "tab_cronus_dash",
        "group": "ui_grp_a",
        "name": "A Bed 타임라인(통합)",
        "order": 10,
        "width": 12,
        "height": ha,
        "format": _fmt_stack("a", ch_a, lb_a, col_a),
    }
    new_b = {
        "id": "ui_tpl_hist_stack_b",
        "type": "ui_template",
        "z": "tab_cronus_dash",
        "group": "ui_grp_b",
        "name": "B Bed 타임라인(통합)",
        "order": 10,
        "width": 12,
        "height": hb,
        "format": _fmt_stack("b", ch_b, lb_b, col_b),
    }
    new_c = {
        "id": "ui_tpl_hist_stack_c",
        "type": "ui_template",
        "z": "tab_cronus_dash",
        "group": "ui_grp_c",
        "name": "C Bed 타임라인(통합)",
        "order": 10,
        "width": 12,
        "height": hc,
        "format": _fmt_stack("c", ch_c, lb_c, col_c),
    }
    new_d = {
        "id": "ui_tpl_hist_stack_d",
        "type": "ui_template",
        "z": "tab_cronus_dash",
        "group": "ui_grp_d",
        "name": "D Bed 타임라인(통합)",
        "order": 10,
        "width": 12,
        "height": hd,
        "format": _fmt_stack("d", ch_d, lb_d, col_d),
    }
    have = {n.get("id") for n in d if isinstance(n, dict)}
    for n in d:
        if n.get("id") == "ui_tpl_hist_stack_a":
            n["format"] = new_a["format"]
            n["height"] = new_a["height"]
        if n.get("id") == "ui_tpl_hist_stack_b":
            n["format"] = new_b["format"]
            n["height"] = new_b["height"]
        if n.get("id") == "ui_tpl_hist_stack_c":
            n["format"] = new_c["format"]
            n["height"] = new_c["height"]
        if n.get("id") == "ui_tpl_hist_stack_d":
            n["format"] = new_d["format"]
            n["height"] = new_d["height"]
    if "ui_tpl_hist_stack_a" not in have:
        d.append(new_a)
    if "ui_tpl_hist_stack_b" not in have:
        d.append(new_b)
    if "ui_tpl_hist_stack_c" not in have:
        d.append(new_c)
    if "ui_tpl_hist_stack_d" not in have:
        d.append(new_d)

    for n in d:
        if n.get("id") == "ui_grp_gh_data" and n.get("type") == "ui_group":
            n["name"] = "센서 Data"
        if n.get("id") == "nr_node_ui_ai_stream":
            n["format"] = AI_FMT
            n["height"] = 8
        if n.get("id") == "ui_tpl_css_cronus":
            fmt = _repair_ui_tpl_css_cronus_format((n.get("format") or ""))
            if "cf-bed-hist-box" in fmt:
                fmt = RE_BED_HIST_CSS_BLOCK.sub(BED_HIST_CSS.strip() + "\n", fmt, count=1)
            if "cf-sched-def-box" not in fmt and "</style>" in fmt:
                fmt = fmt.replace("</style>", SCHED_DEF_CSS.strip() + "\n</style>", 1)
            elif "cf-bed-hist-box" not in fmt:
                fmt = fmt.rstrip()
                if fmt.endswith("</style>"):
                    fmt = fmt[:-8].rstrip() + CSS_INJECT + "\n</style>"
            if CLOCK_INJECT_MARK not in fmt:
                fmt = fmt.rstrip() + "\n" + CLOCK_CSS_BLOCK + "\n"
            fmt = _inject_or_refresh_gh_gauge_css(fmt)
            n["format"] = fmt

    DASH.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    flow_path = ROOT / "nodered" / "CronusFarm_NodeRED_flow.json"
    if flow_path.is_file():
        flow = json.loads(flow_path.read_text(encoding="utf-8-sig"))
        nf = _apply_hist_nodes(
            flow, ch_a, lb_a, col_a, ch_b, lb_b, col_b, ch_c, lb_c, col_c, ch_d, lb_d, col_d
        )
        nd = _remove_sched_defaults_monitor(flow)
        flow_path.write_text(
            json.dumps(flow, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        print("OK", flow_path.name, "hist nodes", nf, "sched monitor removed", nd)
    ng = patch_nginx()
    print("OK dashboard bed A~D stacks + AI; nginx ai-mjpeg:", "patched" if ng else "skip")


if __name__ == "__main__":
    main()
