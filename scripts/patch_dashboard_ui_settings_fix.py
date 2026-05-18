# -*- coding: utf-8 -*-
"""모니터 tele/MQTT UI + 설정 iframe 리사이즈(겹침) + Arduino 위젯 순서."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
T = ROOT / "nodered" / "dashboard"

IFRAME_RESIZE_JS = (
    '<script type="text/javascript">\n'
    "(function(){\n"
    '  window.addEventListener("message",function(ev){\n'
    "    var d=ev.data;\n"
    '    if(!d||d.type!=="cf-settings-iframe-resize"||!d.height)return;\n'
    '    var h=Math.max(320,parseInt(d.height,10)+24)+"px";\n'
    '    var id=d.iframe||"";\n'
    '    document.querySelectorAll(".cf-settings-iframe-wrap").forEach(function(wrap){\n'
    '      var ifr=wrap.querySelector("iframe");\n'
    "      if(!ifr)return;\n"
    "      if(id){ if(wrap.getAttribute(\"data-cf-iframe\")===id) ifr.style.height=h; return; }\n"
    "      if(ev.source&&ifr.contentWindow===ev.source) ifr.style.height=h;\n"
    "    });\n"
    "  },false);\n"
    "})();\n"
    "</script>"
)

IFRAME_MAP = {
    "ui_tpl_settings_beds_iframe": ("beds", "cronusfarm_d1_settings_beds_sched.html"),
    "ui_tpl_settings_sched_ov_iframe": ("sched_ov", "cronusfarm_d1_settings_sched_overview.html"),
    "ui_tpl_settings_tools_iframe": ("tools", "cronusfarm_d1_settings_tools.html"),
}


def patch_hint_bar(fmt: str) -> str:
    return fmt.replace(
        "background:rgba(79,140,255,.08);border:1px solid rgba(79,140,255,.22)",
        "background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06)",
    ).replace("padding:5px 10px", "padding:4px 8px").replace("line-height:1.35", "line-height:1.3")


def patch_mqtt(fmt: str) -> str:
    extra = (
        "\n.cf-r4-mqtt-tile{margin:0;padding:0;line-height:1.2}\n"
        ".cf-r4-mqtt-tile .cf-r4-status-bar{padding:5px 10px}\n"
        ".nr-dashboard-template:has(.cf-r4-mqtt-tile),\n"
        ".nr-dashboard-template:has(.cf-r4-mqtt-tile) md-card{min-height:0!important;height:auto!important}\n"
        ".nr-dashboard-template:has(.cf-r4-mqtt-tile) md-card-content{padding:4px 10px!important;min-height:0!important;height:auto!important}\n"
    )
    if "has(.cf-r4-mqtt-tile) md-card-content" not in fmt:
        fmt = fmt.replace("</style>", extra + "</style>")
    fmt = fmt.replace("margin:4px 0 0!important", "margin:2px 0 0!important")
    return fmt


def patch_guard(fmt: str) -> str:
    fmt = re.sub(r"margin:0 0 \d+px", "margin:0", fmt)
    if "has(.cf-tele-guard-ui) md-card-content" not in fmt:
        extra = (
            "\n.nr-dashboard-template:has(.cf-tele-guard-ui),\n"
            ".nr-dashboard-template:has(.cf-tele-guard-ui) md-card{min-height:0!important;height:auto!important}\n"
            ".nr-dashboard-template:has(.cf-tele-guard-ui) md-card-content{padding:3px 10px!important;min-height:0!important;height:auto!important;margin-bottom:0!important}\n"
        )
        fmt = fmt.replace("</style>", extra + "</style>")
    return fmt


def patch_sum(fmt: str) -> str:
    if "cf-tele-sum-mid" not in fmt:
        fmt = fmt.replace('class="cf-tele-sum-ui"', 'class="cf-tele-sum-ui cf-tele-sum-mid"', 1)
    extra = (
        "\n.cf-tele-sum-mid{margin-top:0!important}\n"
        ".nr-dashboard-template:has(.cf-tele-sum-ui),\n"
        ".nr-dashboard-template:has(.cf-tele-sum-ui) md-card{min-height:0!important;height:auto!important}\n"
        ".nr-dashboard-template:has(.cf-tele-sum-ui) md-card-content{padding:4px 10px!important;min-height:0!important;height:auto!important;margin:0!important}\n"
    )
    if "has(.cf-tele-sum-ui) md-card-content" not in fmt:
        fmt = fmt.replace("</style>", extra + "</style>")
    return fmt


def patch_raw(fmt: str) -> str:
    fmt = fmt.replace("margin:2px 0 0", "margin:0")
    fmt = fmt.replace("gap:1px", "gap:2px")
    if "has(.cf-tele-raw-ui) md-card-content" not in fmt:
        extra = (
            "\n.nr-dashboard-template:has(.cf-tele-raw-ui),\n"
            ".nr-dashboard-template:has(.cf-tele-raw-ui) md-card{min-height:0!important;height:auto!important}\n"
            ".nr-dashboard-template:has(.cf-tele-raw-ui) md-card-content{padding:4px 10px!important;min-height:0!important;height:auto!important;margin-top:0!important}\n"
        )
        fmt = fmt.replace("</style>", extra + "</style>")
    return fmt


def patch_iframe_node(fmt: str, iframe_id: str) -> str:
    fmt = re.sub(r"<script type=\"text/javascript\">[\s\S]*?</script>\s*$", "", fmt).rstrip()
    if 'data-cf-iframe="' not in fmt:
        fmt = fmt.replace(
            '<motion class="cf-settings-iframe-wrap">',
            f'<div class="cf-settings-iframe-wrap" data-cf-iframe="{iframe_id}">',
        )
        fmt = fmt.replace('<div class="cf-settings-iframe-wrap">', f'<motion class="cf-settings-iframe-wrap" data-cf-iframe="{iframe_id}">', 1)
    fmt = re.sub(r'data-cf-iframe="[^"]*"', f'data-cf-iframe="{iframe_id}"', fmt, count=1)
    return fmt + IFRAME_RESIZE_JS


def patch_html_postmessage(path: Path, iframe_id: str) -> None:
    txt = path.read_text(encoding="utf-8")
    old = "parent.postMessage({ type: 'cf-settings-iframe-resize', height: h }, '*');"
    new = f"parent.postMessage({{ type: 'cf-settings-iframe-resize', height: h, iframe: '{iframe_id}' }}, '*');"
    if old in txt:
        txt = txt.replace(old, new)
    elif "iframe:" not in txt and "cf-settings-iframe-resize" in txt:
        txt = txt.replace(
            "type: 'cf-settings-iframe-resize', height: h",
            f"type: 'cf-settings-iframe-resize', height: h, iframe: '{iframe_id}'",
        )
    path.write_text(txt, encoding="utf-8")


def main() -> None:
    data = json.loads(DASH.read_text(encoding="utf-8-sig"))
    by = {n["id"]: n for n in data if isinstance(n, dict) and n.get("id")}

    tpl_fmt = {
        "ui_tpl_conn_line": patch_hint_bar,
        "ui_tpl_status_line": patch_mqtt,
        "ui_tpl_tele_guard": patch_guard,
        "ui_tpl_arduino_led_tele": patch_sum,
        "ui_txt_tele_raw": patch_raw,
    }
    for nid, fn in tpl_fmt.items():
        n = by.get(nid)
        if n and n.get("format"):
            n["format"] = fn(n["format"])

    if by.get("ui_tpl_tele_guard"):
        by["ui_tpl_tele_guard"]["height"] = 1
    if by.get("ui_tpl_status_line"):
        by["ui_tpl_status_line"]["height"] = 1

    orders = {
        "ui_tpl_arduino_led_tele": 8,
        "ui_tpl_tele_guard": 7,
        "ui_txt_tele_raw": 9,
        "ui_txt_cmd_preview": 10,
    }
    for nid, ordv in orders.items():
        if by.get(nid):
            by[nid]["order"] = ordv

    for nid, (iframe_id, html_name) in IFRAME_MAP.items():
        n = by.get(nid)
        if not n:
            continue
        n["format"] = patch_iframe_node(n.get("format") or "", iframe_id)
        hp = T / html_name
        if hp.is_file():
            patch_html_postmessage(hp, iframe_id)

    patch_sched_overview_timeline()

    DASH.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("OK patch_dashboard_ui_settings_fix")
    merge = ROOT / "scripts" / "merge_nodered_deploy.py"
    if merge.is_file():
        r = subprocess.run([sys.executable, str(merge), "--use-split"], cwd=str(ROOT))
        if r.returncode != 0:
            raise SystemExit("merge 실패")


def patch_sched_overview_timeline() -> None:
    path = T / "cronusfarm_d1_settings_sched_overview.html"
    txt = path.read_text(encoding="utf-8")
    if "timeline/batch" in txt:
        print("sched overview: timeline already patched")
        return

    draw_old = "function cfDrawSch24h(canvas, rules) {"
    draw_new = """function cfDrawTimelineExec(ctx, padL, plotW, plotH, padT, anchorMs, nowMs, points) {
  if (!points || points.length < 2) return;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i], p1 = points[i + 1];
    if (Number(p0.state) !== 1) continue;
    const t0 = Math.max(anchorMs, Number(p0.ts_ms));
    const t1 = Math.min(nowMs, Number(p1.ts_ms));
    if (t1 <= t0) continue;
    const x1 = padL + ((t0 - anchorMs) / (nowMs - anchorMs)) * plotW;
    const x2 = padL + ((t1 - anchorMs) / (nowMs - anchorMs)) * plotW;
    const w = Math.max(1, x2 - x1);
    ctx.fillStyle = 'rgba(255,214,10,.55)';
    ctx.fillRect(x1, padT + 1, w, plotH - 2);
    ctx.strokeStyle = '#ffd60a';
    ctx.lineWidth = 1;
    ctx.strokeRect(x1, padT + 1, w, plotH - 2);
  }
}

function cfDrawSch24h(canvas, rules, execData) {"""
    txt = txt.replace(draw_old, draw_new)

    txt = txt.replace(
        "      if (off > 0) drawSeg(0, off, color);\n    }\n  }\n}",
        "      if (off > 0) drawSeg(0, off, color);\n    }\n  }\n  if (execData && execData.points && execData.points.length) {\n    cfDrawTimelineExec(ctx, padL, plotW, plotH, padT, execData.anchor_ts_ms || (Date.now() - 86400000), Date.now(), execData.points);\n  }\n}",
    )

    foot = "색 막대=켜짐"
    if "노란" not in txt:
        txt = txt.replace(foot, "녹색=스케줄 켜짐 · 노란=실제 동작(tele)")

    load_block = """      this.loading = true;
      const o = location.origin || '';
      await Promise.all(this.rows.map(async row => {"""
    load_new = """      this.loading = true;
      const o = location.origin || '';
      const tlUrl = o + API + '/api/channel/timeline/batch?device_id=' + encodeURIComponent(this.deviceId) + '&channels=' + encodeURIComponent(CF_SCH_CHANNELS.join(',')) + '&hours=24';
      let tlMap = {};
      try {
        const tr = await fetch(tlUrl, { credentials: 'same-origin' });
        if (tr.ok) tlMap = (await tr.json()).channels || {};
      } catch (e) { console.warn(e); }
      await Promise.all(this.rows.map(async row => {"""
    txt = txt.replace(load_block, load_new)

    txt = txt.replace(
        "          if (canvas) cfDrawSch24h(canvas, row.rules);",
        "          if (canvas) cfDrawSch24h(canvas, row.rules, tlMap[row.key]);",
    )

    path.write_text(txt, encoding="utf-8")
    print("OK sched overview timeline overlay")


if __name__ == "__main__":
    main()
