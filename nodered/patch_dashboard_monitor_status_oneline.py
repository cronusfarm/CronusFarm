# -*- coding: utf-8 -*-
"""모니터 Arduino 상태 4행: 한 줄(펌프가드 높이) + 점 online/offline."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

FN_CALC = "fn_calc_online"
CSS_NODE = "ui_tpl_css_cronus"

ROW_CSS = """
.cf-r4-line{display:flex!important;align-items:center!important;gap:6px!important;flex-wrap:nowrap!important;
padding:0!important;margin:0!important;line-height:1.1!important;height:1.15em!important;max-height:1.35em!important;
white-space:nowrap!important;width:100%!important;box-sizing:border-box!important;overflow:hidden!important;}
.cf-r4-line .cf-label{font-size:11px;font-weight:700;color:var(--cf-text,#e6edf7);flex:0 0 auto;max-width:8.5em;}
.cf-r4-line .cf-hint{font-size:10px;color:var(--cf-muted,#9db0cc);flex:1 1 auto;overflow:hidden;text-overflow:ellipsis;}
.cf-r4-line .cf-dot{flex:0 0 auto;width:8px;height:8px;margin:0;}
.cf-r4-line .cf-st{font-size:11px;font-weight:700;color:var(--cf-text,#e6edf7);flex:0 0 auto;}
.nr-dashboard-theme .nr-dashboard-template:has(.cf-r4-line) md-card-content,
.nr-dashboard-theme .nr-dashboard-group:has(.cf-r4-line) md-card-content{
  padding:2px 8px!important;min-height:0!important;line-height:1.1!important;}
"""

TPL = {
    "ui_tpl_conn_line": (
        "R4 연결 (WiFi)",
        "msg._wifiIp ? ('ip ' + msg._wifiIp) : (msg._wifiHint || 'W: —')",
        "msg._wifiOk ? 'cf-dot-on' : 'cf-dot-off'",
        "msg._wifiOk ? 'online' : 'offline'",
    ),
    "ui_tpl_status_line": (
        "R4 MQTT (WiFi)",
        "'Mosquitto tele' + (msg.teleAge != null ? ' · ' + msg.teleAge + 's' : '')",
        "msg._ok ? 'cf-dot-on' : 'cf-dot-off'",
        "(msg._ok ? 'online' : 'offline') + (msg.teleAge != null ? ' · ' + msg.teleAge + 's' : '')",
    ),
    "ui_tpl_r3_panel_line": (
        "R3 패널 (I2C)",
        "msg._r3hint || 'tele P: —'",
        "msg._r3ok === true ? 'cf-dot-on' : (msg._r3ok === false ? 'cf-dot-off' : '')",
        "(msg._r3ok === true ? 'online' : (msg._r3ok === false ? 'offline' : '—'))",
    ),
    "ui_tpl_r4_usb_line": (
        "MQTT USB (시리얼)",
        "'USB tele' + (msg._usbAge != null ? ' · ' + msg._usbAge + 's' : ' · 미수신')",
        "msg._usbOk ? 'cf-dot-on' : 'cf-dot-off'",
        "(msg._usbOk ? 'online' : 'offline') + (msg._usbAge != null ? ' · ' + msg._usbAge + 's' : '')",
    ),
}


def _row(label: str, hint_expr: str, dot: str, state: str) -> str:
    return (
        f'<div class="cf-r4-line">'
        f'<span class="cf-label">{label}</span>'
        f'<span class="cf-hint" ng-bind="{hint_expr}"></span>'
        f'<div class="cf-dot" ng-class="{dot}"></div>'
        f'<span class="cf-st" ng-bind="{state}"></span>'
        f"</div>"
    )


def main() -> int:
    data = json.loads(DASH.read_text(encoding="utf-8-sig"))
    by = {n["id"]: n for n in data if isinstance(n, dict) and n.get("id")}

    css = by.get(CSS_NODE)
    if css and ROW_CSS.strip() not in (css.get("format") or ""):
        fmt = css.get("format") or ""
        if "</style>" in fmt:
            fmt = fmt.replace("</style>", ROW_CSS + "\n</style>", 1)
        else:
            fmt += f"<style>{ROW_CSS}</style>"
        css["format"] = fmt

    calc = by.get(FN_CALC)
    if calc:
        calc["outputs"] = 4
        calc["wires"] = [
            ["ui_tpl_conn_line"],
            ["ui_tpl_status_line"],
            ["ui_tpl_r3_panel_line"],
            ["ui_tpl_r4_usb_line"],
        ]

    orders = {
        "ui_tpl_conn_line": 3,
        "ui_tpl_status_line": 4,
        "ui_tpl_r3_panel_line": 5,
        "ui_tpl_r4_usb_line": 6,
    }
    for nid, spec in TPL.items():
        n = by.get(nid)
        if not n:
            continue
        n["format"] = _row(*spec)
        n["group"] = "ui_grp_arduino"
        n["width"] = "12"
        n["height"] = 1
        n["order"] = orders.get(nid, 9)

    DASH.write_text(json.dumps(list(by.values()), ensure_ascii=False), encoding="utf-8")
    print("OK patch_dashboard_monitor_status_oneline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
