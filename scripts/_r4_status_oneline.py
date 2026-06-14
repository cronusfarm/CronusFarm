# -*- coding: utf-8 -*-
"""R4 상태 행 + farm 경로 요약 — cf-srv-inlay 한 줄 표기."""
from __future__ import annotations

ROW_CSS_MARK = "/* cf-r4-status */"


def _p(expr: str) -> str:
    return f"(msg.payload && msg.payload.{expr})"


def inlay_row_one_line(line_expr: str, dot_expr: str, state_expr: str) -> str:
    return (
        '<div class="cf-srv-inlay">'
        '<div class="cf-srv-inlay-bar">'
        '<div class="cf-srv-inlay-text cf-srv-inlay-text--compact">'
        f'<div class="cf-srv-inlay-title cf-srv-inlay-title--one" ng-bind="{line_expr}"></div>'
        "</div>"
        '<div class="cf-srv-inlay-status">'
        f'<div class="cf-dot" ng-class="{dot_expr}"></div>'
        f'<span class="cf-srv-inlay-st" ng-bind="{state_expr}"></span>'
        "</div></div></div>"
    )


def farm_route_summary_fmt() -> str:
    ng_cls = (
        "{'cf-route-ok': "
        + _p("controlOk")
        + " && !"
        + _p("degraded")
        + ", 'cf-route-warn': "
        + _p("controlOk")
        + " && "
        + _p("degraded")
        + ", 'cf-route-bad': !"
        + _p("controlOk")
        + "}"
    )
    dot_cls = (
        _p("controlOk")
        + " ? ("
        + _p("degraded")
        + " ? 'cf-dot-warn' : 'cf-dot-on') : 'cf-dot-off'"
    )
    return (
        f'<div class="cf-srv-inlay cf-route-sum" ng-class="{ng_cls}">'
        '<div class="cf-srv-inlay-bar">'
        '<div class="cf-srv-inlay-text">'
        f'<div class="cf-srv-inlay-title" ng-bind="{_p("routeTitle")}"></div>'
        f'<div class="cf-srv-inlay-sub" ng-bind="{_p("routeDetail")}"></div>'
        "</div>"
        '<div class="cf-srv-inlay-status">'
        f'<div class="cf-dot" ng-class="{dot_cls}"></div>'
        f'<span class="cf-srv-inlay-st" ng-bind="{_p("controlState")}"></span>'
        "</div></div></div>"
    )


# (한 줄 본문 expr, dot expr, state expr)
LINE_SPECS: dict[str, tuple[str, str, str]] = {
    "ui_tpl_farm_route_summary": (
        "",
        "",
        "",
    ),
    "ui_tpl_conn_line": (
        "'R4 WiFi (디바이스) · ' + ("
        f"{_p('wifiIp')} ? ('ip ' + {_p('wifiIp')}) : ({_p('wifiHint')} || 'ip 없음')"
        ")",
        f"{_p('wifiDeviceOk')} ? 'cf-dot-on' : 'cf-dot-off'",
        f"{_p('wifiDeviceOk')} ? 'online' : 'offline'",
    ),
    "ui_tpl_r4_usb_line": (
        "'farm primary (USB tele) · ' + ("
        f"{_p('usbAge')} != null ? {_p('usbAge')} + 's' : '미수신'"
        ")",
        f"{_p('usbFarmOk')} ? 'cf-dot-on' : 'cf-dot-off'",
        f"{_p('usbFarmOk')} ? 'online' : 'offline'",
    ),
    "ui_tpl_status_line": (
        "'farm 백업 (WiFi MQTT) · tele' + ("
        f"{_p('mqttTeleAge')} != null ? ' · ' + {_p('mqttTeleAge')} + 's' : ' · —'"
        ")",
        f"{_p('mqttWifiFarmOk')} ? 'cf-dot-on' : 'cf-dot-off'",
        f"{_p('mqttWifiFarmOk')} ? 'online' : 'offline'",
    ),
    "ui_tpl_r3_panel_line": (
        "'R3 패널 (I2C) · ' + ("
        f"{_p('r3hint')} || 'tele P: —'"
        ")",
        f"{_p('r3ok')} === true ? 'cf-dot-on' : ({_p('r3ok')} === false ? 'cf-dot-off' : '')",
        f"({_p('r3ok')} === true ? 'online' : ({_p('r3ok')} === false ? 'offline' : '—'))",
    ),
}

ORDERS = {
    "ui_tpl_farm_route_summary": 2,
    "ui_tpl_conn_line": 3,
    "ui_tpl_r4_usb_line": 4,
    "ui_tpl_status_line": 5,
    "ui_tpl_r3_panel_line": 6,
}

LABELS = {
    "ui_tpl_farm_route_summary": "farm 제어 경로",
    "ui_tpl_conn_line": "R4 WiFi (디바이스)",
    "ui_tpl_r4_usb_line": "farm primary (USB)",
    "ui_tpl_status_line": "farm 백업 (WiFi MQTT)",
    "ui_tpl_r3_panel_line": "R3 패널 (I2C)",
}

TELE_GUARD_FMT = inlay_row_one_line(
    "'펌프 가드 (tele G:)'",
    "{'cf-dot-on': (msg.payload||'').toString()==='ok', 'cf-dot-off': (msg.payload||'').toString()!=='ok' && (msg.payload||'').toString().indexOf('—')!==0}",
    "(msg.payload||'').toString()",
)


def formats() -> dict[str, str]:
    out = {nid: inlay_row_one_line(*spec) for nid, spec in LINE_SPECS.items() if spec[0]}
    out["ui_tpl_farm_route_summary"] = farm_route_summary_fmt()
    return out
