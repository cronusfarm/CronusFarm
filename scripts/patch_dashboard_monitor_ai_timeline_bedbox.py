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

CSS_INJECT = """
/* AI 카메라: 높이 확보 + 캡션 오버레이 + 잘림 방지 */
.nr-dashboard-theme .cf-ai-cam-outer{position:relative;width:100%;display:inline-block;max-width:100%;vertical-align:top;}
.nr-dashboard-theme .cf-ai-cam-root{width:100%;position:relative;text-align:center;}
.nr-dashboard-theme .cf-ai-cam-root img{max-width:100%;width:auto;height:auto;object-fit:contain;display:block;margin:0 auto;transform:scaleX(-1);}
.nr-dashboard-theme .cf-ai-cam-caption{position:absolute;left:0;right:0;bottom:0;z-index:3;padding:8px 10px;font-size:13px;font-weight:800;color:#e8f5e9;text-align:center;line-height:1.35;pointer-events:none;text-shadow:0 1px 3px rgba(0,0,0,.95);background:linear-gradient(180deg,transparent,rgba(0,0,0,.82));}
.nr-dashboard-theme .nr-dashboard-group:has(.cf-ai-cam-outer) .nr-dashboard-template,
body.nr-dashboard-theme md-card:has(.cf-ai-cam-outer) .nr-dashboard-template{overflow:visible!important;max-height:none!important;height:auto!important;}
""" + BED_HIST_CSS

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


# 툴바 시계: body MutationObserver + textContent 갱신이 상호 재진입해 /ui 탭 멈춤 → Observer 미사용, mount만 저빈도
MONITOR_CLOCK_BOOT = r"""<script type="text/javascript">
(function(){
  if(window.__cfMonitorToolbarClock)return; window.__cfMonitorToolbarClock=1;
  var ID="cf-monitor-tab-clock";
  var NEEDLE="CronusFarm";
  function findToolbarTools(){
    var list=document.querySelectorAll("md-toolbar .md-toolbar-tools");
    for(var i=0;i<list.length;i++){
      var el=list[i];
      if(el.querySelector("md-tabs") && (el.textContent||"").indexOf(NEEDLE)>=0) return el;
    }
    return document.querySelector("md-toolbar .md-toolbar-tools");
  }
  function tick(){
    var el=document.getElementById(ID);
    if(!el) return;
    el.textContent=new Date().toLocaleString("ko-KR",{
      year:"numeric",month:"2-digit",day:"2-digit",
      hour:"2-digit",minute:"2-digit",second:"2-digit",hour12:false
    });
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
  setInterval(tick,1000);
  setInterval(mount,8000);
  setTimeout(mount,0);
})();
</script>
"""

AI_FMT = MONITOR_CLOCK_BOOT + r"""<div class="cf-ai-cam-outer">
  <div class="cf-ai-cam-root" style="width:100%;background:#050a12;text-align:center;">
    <img id="cf-ai-mjpeg-img" alt="AI camera" src="/farm/ai-mjpeg/video_feed" style="max-width:100%;width:auto;height:auto;object-fit:contain;display:block;margin:0 auto;background:#000;"/>
  </div>
  <div id="cf-ai-cap-txt" class="cf-ai-cam-caption">실시간 온실 영상 (로딩)</div>
</div>
<script type="text/javascript">
(function(scope){
  function setCap(v){
    var t=document.getElementById("cf-ai-cap-txt");
    if(!t||v==null||v==="")return;
    if(typeof v==="object"&&v!==null){
      if(v.caption!=null&&String(v.caption).trim()){ t.textContent=String(v.caption).trim(); return; }
      return;
    }
    t.textContent=String(v);
  }
  if(typeof scope!=="undefined"&&scope&&typeof scope.$watch==="function"){
    scope.$watch("msg", function(m){ if(m)setCap(m.payload); }, true);
  }
  var el=document.getElementById("cf-ai-mjpeg-img");
  if(!el)return;
  var h=location.hostname||"127.0.0.1";
  var pr=location.protocol||"http:";
  var p=String(location.port||"");
  if(p==="1882"||p==="1884"){el.src=pr+"//"+h+":8080/stream";}
  else{el.src=(location.origin||"")+"/farm/ai-mjpeg/video_feed";}
})(scope);
</script>"""

# Bed 타임라인 카드 제목(스택 HTML)
_BED_HIST_TITLE = {"a": "A Bed", "b": "B Bed", "c": "C Bed", "d": "D Bed"}


def _fill_rgba(hex_color: str, alpha: float = 0.38) -> str:
    """ON 구간 채우기용 — 선색과 동일 톤의 반투명 배경."""
    h = (hex_color or "").strip().lstrip("#")
    if len(h) != 6 or not all(c in "0123456789abcdefABCDEF" for c in h):
        return f"rgba(127,127,127,{alpha})"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _nr_bed_hist_height(num_channels: int) -> int:
    """Node-RED Dashboard ui_template height(그리드 단): 제목 1 + 채널당 1, 하단 빈칸 최소화."""
    return max(3, 1 + int(num_channels))


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
    fills_json = json.dumps([_fill_rgba(c) for c in colors], ensure_ascii=False)
    title = _BED_HIST_TITLE.get(bed, bed.upper() + " Bed")
    return f"""<div class="cf-bed-hist-box">
  <div class="cf-bed-hist-hd">{title} — 24h ON/OFF</div>
  <div class="cf-bed-hist-stack">
    {rows_html}
  </div>
</div>
<script src="/cronusfarm-static/vendor/chart.umd.min.js"></script>
<script type="text/javascript">
(function(scope) {{
  const BED = {json.dumps(bed)};
  const CHANNELS = {ch_json};
  const LABELS = {lb_json};
  const COLS = {col_json};
  const FILLS = {fills_json};
  const API = (location.origin || '') + '/farm/cronusfarm-sqlite/api/channel/timeline';
  const charts = [];
  function deviceId() {{
    try {{ const s = localStorage.getItem('cfDeviceId'); if (s && s.trim()) return s.trim(); }} catch (e) {{}}
    return 'cronusfarm-01';
  }}
  function mapTime(j) {{
    /* API anchor_ts_ms 대신 window_end·hours로만 창 고정(정확히 N시간 롤링) */
    const tEnd = (j.window_end_ms != null && isFinite(Number(j.window_end_ms))) ? Number(j.window_end_ms) : Date.now();
    const h = Number(j.hours);
    const hrs = (isFinite(h) && h >= 1 && h <= 168) ? h : 24;
    return {{ tStart: tEnd - hrs * 3600 * 1000, tEnd: tEnd }};
  }}
  async function loadOne(i) {{
    const ch = CHANNELS[i];
    const el = document.getElementById('cf_hc_' + BED + '_' + ch);
    if (!el) return;
    try {{
      const u = API + '?device_id=' + encodeURIComponent(deviceId()) + '&channel=' + encodeURIComponent(ch) + '&hours=24';
      const r = await fetch(u, {{ credentials: 'same-origin' }});
      if (!r.ok) return;
      const j = await r.json();
      const tt = mapTime(j);
      const x0 = Number(tt.tStart);
      const x1 = Number(tt.tEnd);
      const pts = j.points || [];
      const data = pts.map(function(p) {{
        return {{ x: Number(p.ts_ms), y: (p.state === 1 || p.state === true) ? 1 : 0 }};
      }});
      data.sort(function(a, b) {{ return a.x - b.x; }});
      /* X축 시간 라벨 6개: 구간을 5등분한 stepSize + autoSkip 끔 */
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
          data: {{ datasets: [{{ label: LABELS[i], data: data, parsing: false, stepped: true, borderWidth: 1.5, borderColor: COLS[i], backgroundColor: FILLS[i], fill: true, pointRadius: 0 }}]}},
          options: opt
        }});
      }} else {{
        charts[i].data.datasets[0].data = data;
        charts[i].data.datasets[0].borderColor = COLS[i];
        charts[i].data.datasets[0].backgroundColor = FILLS[i];
        charts[i].options.scales.x.min = x0;
        charts[i].options.scales.x.max = x1;
        charts[i].options.scales.x.ticks.stepSize = xTickStep;
        charts[i].update();
      }}
    }} catch (e) {{ console.warn(e); }}
  }}
  async function loadAll() {{
    for (let i = 0; i < CHANNELS.length; i++) await loadOne(i);
  }}
  scope.$watch('msg', function() {{ loadAll(); }});
  setInterval(loadAll, 60000);
  setTimeout(loadAll, 700);
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


def main() -> None:
    d = json.loads(DASH.read_text(encoding="utf-8-sig"))
    d = [n for n in d if n.get("id") not in REMOVE_IDS]

    ch_a = ["led_a1", "led_a2", "pump_a1", "pump_a2", "fan_a1", "fan_a2"]
    lb_a = ["LED A1", "LED A2", "Pump A1", "Pump A2", "Fan A1", "Fan A2"]
    col_a = ["#FFD54F", "#FFC107", "#42A5F5", "#1E88E5", "#66BB6A", "#43A047"]

    ch_b = ["led_b1", "led_b2", "pump_b1", "pump_b2", "fan_b1", "fan_b2"]
    lb_b = ["LED B1", "LED B2", "Pump B1", "Pump B2", "Fan B1", "Fan B2"]
    col_b = ["#FFD54F", "#FFC107", "#42A5F5", "#1E88E5", "#66BB6A", "#43A047"]

    ch_c = ["pump_c1", "pump_c2"]
    lb_c = ["Pump C1", "Pump C2"]
    col_c = ["#42A5F5", "#1E88E5"]

    ch_d = ["pump_d1", "pump_d2"]
    lb_d = ["Pump D1", "Pump D2"]
    col_d = ["#42A5F5", "#1E88E5"]

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
            n["height"] = 12
        if n.get("id") == "ui_tpl_css_cronus":
            fmt = _repair_ui_tpl_css_cronus_format((n.get("format") or ""))
            if "cf-bed-hist-box" in fmt:
                fmt = RE_BED_HIST_CSS_BLOCK.sub(BED_HIST_CSS.strip() + "\n", fmt, count=1)
            elif "cf-bed-hist-box" not in fmt:
                fmt = fmt.rstrip()
                if fmt.endswith("</style>"):
                    fmt = fmt[:-8].rstrip() + CSS_INJECT + "\n</style>"
            if CLOCK_INJECT_MARK not in fmt:
                fmt = fmt.rstrip() + "\n" + CLOCK_CSS_BLOCK + "\n"
            fmt = _inject_or_refresh_gh_gauge_css(fmt)
            n["format"] = fmt

    DASH.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    ng = patch_nginx()
    print("OK dashboard bed A~D stacks + AI; nginx ai-mjpeg:", "patched" if ng else "skip")


if __name__ == "__main__":
    main()
