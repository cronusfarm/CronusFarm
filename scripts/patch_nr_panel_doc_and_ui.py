"""Patch Node-RED dashboard + devflow JSON (panel doc link, online dot, pump guard spacing)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
DEV = ROOT / "nodered" / "flows_cronusfarm_devflow_flow.json"

FN_CALC_NEW = r"""const now=Date.now();
const ls=flow.get('arduinoLastStatusMs')||0;
const lt=flow.get('arduinoLastTeleMs')||0;
const TELE_MS=15000;
const teleOk = lt > 0 && (now - lt) < TELE_MS;
function normStatus(v) {
  let s = (v === undefined || v === null) ? '' : String(v);
  s = s.replace(/^\uFEFF/, '').trim().replace(/^['\"]+|['\"]+$/g, '');
  let rl0 = s.toLowerCase();
  if (rl0.charAt(0) === '{') {
    try {
      const o = JSON.parse(s);
      if (o && typeof o.state === 'string') { s = String(o.state).trim(); }
    } catch (e) { /* 무시 */ }
  }
  return s;
}
const retain = normStatus(flow.get('lastStatusStr'));
const rl = retain.toLowerCase();
const retainOn = rl === 'online';
const retainOff = rl === 'offline';
let connOk = false;
if (retainOff) connOk = false;
else if (retainOn) connOk = true;
else if (retain) connOk = teleOk;
else connOk = teleOk;
msg._ok = teleOk;
msg._connOk = connOk;
msg.connLineOk = connOk;
msg.statusAge=ls?Math.floor((now-ls)/1000):null;
msg.teleAge=lt?Math.floor((now-lt)/1000):null;
msg.statusRetain=retain;
const pl=msg.payload;
let raw='';
if(typeof pl==='string'&&pl.length){ raw=pl; }
else { raw=(flow.get('lastTeleStr')||'').toString(); }
msg.telePreview = raw;
msg.payload = raw;
return msg;"""

CONN_OLD = (
    'msg._ok ? \'cf-dot-on\' : \'cf-dot-off\'"></div>'
    '<div style="font-size:12px;color:var(--cf-text);white-space:nowrap;">'
    "{{msg._ok ? 'online' : 'offline'}}"
)
CONN_NEW = (
    'msg._connOk ? \'cf-dot-on\' : \'cf-dot-off\'"></div>'
    '<div style="font-size:12px;color:var(--cf-text);white-space:nowrap;">'
    "{{msg._connOk ? 'online' : 'offline'}}"
)

RAW_DOT_OLD = '<div class="cf-dot" ng-class="msg._ok ? \'cf-dot-on\' : \'cf-dot-off\'"></div>'
RAW_DOT_NEW = '<div class="cf-dot" ng-class="msg._connOk ? \'cf-dot-on\' : \'cf-dot-off\'"></div>'
RAW_HINT_OLD = '<span class="cf-mqtt-hint">retain · …/status · 점=tele 기준</span>'
RAW_HINT_NEW = '<span class="cf-mqtt-hint">retain · …/status · 점=녹색=online</span>'

CSS_INSERT = """
/* cf-guard-tight-v1 — 펌프 가드(G:) Arduino 카드 세로 간격 축소, 세로 스크롤 없음 */
.nr-dashboard-theme .nr-dashboard-group:has(.cf-arduino-conn-tile) .nr-dashboard-template:has(.cf-tele-guard-ui){
  margin-top:0!important;margin-bottom:0!important;padding-top:0!important;padding-bottom:0!important;
}
.nr-dashboard-theme .nr-dashboard-group:has(.cf-arduino-conn-tile) md-card-content .nr-dashboard-template:has(.cf-tele-guard-ui) md-card,
.nr-dashboard-theme .nr-dashboard-group:has(.cf-arduino-conn-tile) .nr-dashboard-template:has(.cf-tele-guard-ui) .nr-dashboard-template{
  margin-top:0!important;margin-bottom:0!important;
}
.cf-tele-guard-ui,.cf-tele-guard-ui *{max-height:none!important;}
.cf-tele-guard-pre{overflow-y:visible!important;overflow-x:visible!important;}
"""

# 펌프 가드(ok) 블록과 바로 아래 tele 미리보기 타일 사이 — NR은 타일마다 md-card라 전역으로 당김
CSS_GUARD_TELE_GAP = """
/* cf-guard-tight-v2 — 가드 ↔ tele 문자열 카드 간격 */
.nr-dashboard-theme .nr-dashboard-group .nr-dashboard-template:has(.cf-tele-guard-ui){margin-bottom:-20px!important;}
.nr-dashboard-theme .nr-dashboard-group .nr-dashboard-template:has(.cf-tele-sum-ui){margin-top:-18px!important;}
"""


def patch_dashboard(data: list) -> int:
    n_changed = 0
    for n in data:
        nid = n.get("id")
        if nid == "fn_calc_online" and n.get("type") == "function":
            if n.get("func") != FN_CALC_NEW:
                n["func"] = FN_CALC_NEW
                n_changed += 1
        if nid == "ui_tpl_conn_line" and n.get("type") == "ui_template":
            fmt = n.get("format", "")
            if CONN_OLD in fmt:
                n["format"] = fmt.replace(CONN_OLD, CONN_NEW)
                n_changed += 1
        if nid == "ui_txt_status_raw" and n.get("type") == "ui_template":
            fmt = n.get("format", "")
            ch = 0
            if RAW_DOT_OLD in fmt:
                fmt = fmt.replace(RAW_DOT_OLD, RAW_DOT_NEW)
                ch += 1
            if RAW_HINT_OLD in fmt:
                fmt = fmt.replace(RAW_HINT_OLD, RAW_HINT_NEW)
                ch += 1
            if ch:
                n["format"] = fmt
                n_changed += ch
        # ui_tpl_tele_guard: patch_srv_inlay_widgets.py 가 단일 정본(FMT_TELE_GUARD) — 여기서 덮어쓰면 간격 패치가 무력화됨
        if nid == "ui_tpl_css_cronus" and n.get("type") == "ui_template":
            fmt = n.get("format", "")
            if "cf-guard-tight-v1" not in fmt:
                if "</style>" in fmt:
                    n["format"] = fmt.replace("</style>", CSS_INSERT + "</style>")
                    n_changed += 1
                    fmt = n["format"]
            if "cf-guard-tight-v2" not in fmt and "</style>" in fmt:
                n["format"] = fmt.replace("</style>", CSS_GUARD_TELE_GAP + "</style>")
                n_changed += 1
    return n_changed


def patch_devflow(data: list) -> int:
    """Insert hardware group + panel doc link; bump existing devflow group order."""
    ids = {n.get("id") for n in data}
    if "cf_grp_dev_hw" in ids:
        return 0
    for n in data:
        if n.get("id") == "ui_grp_devflow" and n.get("type") == "ui_group":
            n["order"] = 2
    doc_href = "cronusfarm_panel_lcd_boot.html"
    tpl = (
        '<div class="cf-dev-hw-panel" style="font-family:system-ui,\'Malgun Gothic\',sans-serif;font-size:12px;line-height:1.45;color:#ececec">'
        '<p style="margin:0 0 8px;font-weight:700;color:#aed581">패널 LCD 표시 상태</p>'
        '<p style="margin:0 0 8px;opacity:.92">R3/R4 부팅 시 2004A 패널에 나오는 화면 순서(한 페이지).</p>'
        f'<p style="margin:0"><a href="{doc_href}" target="_blank" rel="noopener" style="color:#80deea">문서 열기 (패널 부팅 순서)</a>'
        " · 저장소: <code style=\"color:#ffcc80\">nodered/dashboard/cronusfarm_panel_lcd_boot.html</code></p></div>"
    )
    grp = {
        "id": "cf_grp_dev_hw",
        "type": "ui_group",
        "z": "tab_cronus_devflow",
        "name": "하드웨어",
        "tab": "ui_tab_devflow",
        "order": 1,
        "disp": True,
        "width": "12",
        "collapse": False,
    }
    ut = {
        "id": "cf_tpl_dev_hw_panel",
        "type": "ui_template",
        "z": "tab_cronus_devflow",
        "group": "cf_grp_dev_hw",
        "order": 1,
        "width": 0,
        "height": 0,
        "name": "패널 LCD 부팅 순서(문서 링크)",
        "format": tpl,
        "storeOutMessages": True,
        "fwdInMessages": False,
        "resendOnRefresh": True,
        "templateScope": "local",
        "x": 0,
        "y": 0,
        "wires": [[]],
    }
    data.append(grp)
    data.append(ut)
    return 2


def main() -> None:
    dash = json.loads(DASH.read_text(encoding="utf-8"))
    c1 = patch_dashboard(dash)
    DASH.write_text(json.dumps(dash, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    dev = json.loads(DEV.read_text(encoding="utf-8"))
    c2 = patch_devflow(dev)
    DEV.write_text(json.dumps(dev, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print("dashboard patches:", c1, "devflow nodes added:", c2)


if __name__ == "__main__":
    main()
