# -*- coding: utf-8 -*-
"""대시보드 모니터 8건: cmd 미리보기·R4/MQTT·펌프가드·PHW·Pi 도메인."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
MQTT = ROOT / "nodered" / "flows_cronusfarm_mqtt.json"

FLOW_SET_CMD = (
    "flow.set('lastDashboardCmd', (msg.topic || '') + '\\n' + (msg.payload || ''));"
)

FN_CMD_PREVIEW_SHOW = """msg.payload = flow.get('lastDashboardCmd') || '(아직 대시보드에서 보낸 cmd 없음)';
return msg;"""

FMT_CONN = """<div class="cf-r4-status-bar cf-arduino-conn-tile">
  <div class="cf-label">R4 연결</div>
  <div class="cf-r4-status-right">
    <div class="cf-dot" ng-class="msg.connLineOk ? 'cf-dot-on' : 'cf-dot-off'"></div>
    <span class="cf-r4-st">{{msg.connLineOk ? 'online' : 'offline'}}</span>
    <span class="cf-muted">· tele {{msg.teleAge}}s · status 수신 {{msg.statusAge}}s</span>
  </div>
</div>
<p class="cf-ar-hint-bar">내장 매트릭스: 위 = WiFi · 아래 = MQTT (메인 R4)</p>
<style>
.cf-r4-status-bar{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;padding:6px 10px;background:rgba(79,140,255,.08);border:1px solid rgba(79,140,255,.22);border-radius:10px;color:var(--cf-text,#e6edf7);width:100%;box-sizing:border-box}
.cf-r4-status-bar .cf-label{font-size:13px;font-weight:700;color:var(--cf-text,#e6edf7);margin:0}
.cf-r4-status-right{display:flex;align-items:center;gap:8px;flex-shrink:0;white-space:nowrap;font-size:12px;color:var(--cf-text,#e6edf7)}
.cf-r4-st{font-weight:700}
.cf-arduino-conn-tile{margin:0;padding:0;line-height:1.25}
.cf-ar-hint-bar{margin:4px 0 0;padding:5px 10px;font-size:10px;line-height:1.35;color:#e6edf7;background:rgba(79,140,255,.08);border:1px solid rgba(79,140,255,.22);border-radius:8px;box-sizing:border-box}
.nr-dashboard-theme .nr-dashboard-template:has(.cf-r4-status-bar) md-card,
.nr-dashboard-theme .nr-dashboard-template:has(.cf-r4-status-bar) md-card-content{background:transparent!important;color:var(--cf-text,#e6edf7)!important}
</style>"""

FMT_MQTT = r"""<div class="cf-r4-status-bar cf-r4-mqtt-tile">
  <div class="cf-label">R4 MQTT</div>
  <div class="cf-r4-status-right">
    <div class="cf-dot" ng-class="msg.connLineOk ? 'cf-dot-on' : 'cf-dot-off'"></div>
    <span class="cf-r4-st">{{msg.connLineOk ? 'online' : 'offline'}}</span>
    <span class="cf-muted">· retain · …/status · Mosquitto</span>
    <span class="cf-r4-retain" ng-if="msg.statusRetain && msg.statusRetain.length > 0 && msg.statusRetain.toLowerCase() !== 'online' && msg.statusRetain.toLowerCase() !== 'offline'">· {{msg.statusRetain}}</span>
  </div>
</div>
<pre class="cf-mqtt-unified-raw" ng-if="msg.statusRetain && msg.statusRetain.length > 0 && msg.statusRetain.toLowerCase() !== 'online' && msg.statusRetain.toLowerCase() !== 'offline'">{{msg.statusRetain}}</pre>
<style>
.cf-r4-mqtt-tile{margin:0;padding:0}
.cf-r4-retain{font-size:11px;font-weight:600;color:var(--cf-accent,#4f8cff)}
.cf-mqtt-unified-raw{margin:4px 0 0!important;padding:4px 8px!important;font-size:10.5px;line-height:1.35;color:#e6edf7;white-space:pre-wrap;word-break:break-word;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:8px}
</style>"""

FMT_TELE_GUARD = r"""<div class="cf-tele-guard-ui cf-fe-wide cf-arduino-stack-gap0">
  <div class="cf-ar-title-nogap">펌프 가드</div>
  <div class="cf-muted cf-tele-guard-lbl">(tele G:)</div>
  <pre class="cf-tele-guard-pre" ng-class="{'cf-guard-warn': (msg.payload||'').toString().indexOf('mx')>=0 || (msg.payload||'').toString().indexOf('mf')>=0, 'cf-guard-ok': (msg.payload||'').toString()==='ok', 'cf-guard-legacy': (msg.payload||'').toString().indexOf('—')===0}" ng-bind="msg.payload"></pre>
</div>
<style>
.cf-tele-guard-ui{display:flex;flex-direction:column;gap:2px;width:100%!important;max-width:100%!important;box-sizing:border-box;margin:0;padding:0}
.cf-tele-guard-ui .cf-ar-title-nogap{margin:0!important;padding:0!important;line-height:1.15!important;font-size:12px;font-weight:600;color:var(--cf-text,#e6edf7)}
.cf-tele-guard-lbl{margin:0;padding:0;line-height:1.15!important;font-size:11px;color:var(--cf-muted,#9db0cc)}
.cf-tele-guard-pre{display:block;margin:0!important;padding:2px 8px!important;width:100%!important;min-width:0;box-sizing:border-box!important;font-size:11.5px;line-height:1.25;color:#e6edf7;white-space:pre-wrap;word-break:break-word;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.14);border-radius:6px;min-height:1.1em;max-height:1.65em;overflow:auto}
.cf-guard-ok{border-color:rgba(40,167,69,.5)!important;background:rgba(40,167,69,.08)!important}
.cf-guard-warn{border-color:rgba(255,193,7,.6)!important;background:rgba(255,193,7,.1)!important}
.cf-guard-legacy{border-color:rgba(157,176,204,.35)!important;background:rgba(255,255,255,.04)!important}
</style>"""

FN_PI_HOST = """const ts = (env.get('CRONUSFARM_PI_HOST') || 'ida.mango-larch.ts.net').toString().trim();
const duck = (env.get('CRONUSFARM_PI_DUCKDNS') || 'cronusfarm.duckdns.org').toString().trim();
const parts = [];
if (ts) parts.push(ts);
if (duck && duck !== ts) parts.push(duck);
msg.payload = parts.length ? parts.join(' · ') : 'ida.mango-larch.ts.net · cronusfarm.duckdns.org';
return msg;"""

PHW_BAD_ID = "var el=document.getElementById('cf_phw_chart');"
PHW_GOOD = "setMsg('API '+r.status);return;"


def _patch_phw(fmt: str) -> str:
    if PHW_BAD_ID in fmt:
        fmt = fmt.replace(PHW_BAD_ID, PHW_GOOD)
    return fmt


def _ensure_cmd_preview_nodes(data: list) -> None:
    by_id = {n.get("id"): n for n in data if isinstance(n, dict)}
    if "inj_cmd_preview_tick" not in by_id:
        data.append(
            {
                "id": "inj_cmd_preview_tick",
                "type": "inject",
                "z": "tab_cronus_dash",
                "name": "cmd 미리보기 2s",
                "props": [{"p": "payload"}, {"p": "topic", "vt": "str"}],
                "repeat": "2",
                "crontab": "",
                "once": True,
                "onceDelay": 0.4,
                "topic": "",
                "payload": "",
                "payloadType": "date",
                "x": 2680,
                "y": 1040,
                "wires": [["fn_cmd_preview_show"]],
            }
        )
    if "fn_cmd_preview_show" not in by_id:
        data.append(
            {
                "id": "fn_cmd_preview_show",
                "type": "function",
                "z": "tab_cronus_dash",
                "name": "cmd 미리보기 표시",
                "func": FN_CMD_PREVIEW_SHOW,
                "outputs": 1,
                "timeout": 0,
                "noerr": 0,
                "initialize": "",
                "finalize": "",
                "libs": [],
                "x": 2770,
                "y": 1040,
                "wires": [["ui_txt_cmd_preview"]],
            }
        )
    else:
        by_id["fn_cmd_preview_show"]["func"] = FN_CMD_PREVIEW_SHOW
        by_id["fn_cmd_preview_show"]["wires"] = [["ui_txt_cmd_preview"]]


def patch_dashboard() -> None:
    data = json.loads(DASH.read_text(encoding="utf-8-sig"))
    for n in data:
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        if nid == "ui_tpl_conn_line":
            n["format"] = FMT_CONN
        elif nid == "ui_tpl_status_line":
            n["format"] = FMT_MQTT
        elif nid == "ui_tpl_tele_guard":
            n["format"] = FMT_TELE_GUARD
        elif nid == "fn_pi_host":
            n["func"] = FN_PI_HOST
        elif nid == "fn_cmd_merge_v2":
            func = n.get("func") or ""
            if FLOW_SET_CMD not in func:
                func = func.rstrip()
                if func.endswith("return msg;"):
                    func = func[: -len("return msg;")] + FLOW_SET_CMD + "\nreturn msg;"
                else:
                    func += "\n" + FLOW_SET_CMD + "\nreturn msg;"
                n["func"] = func
            n["wires"] = [["mqtt_out_cmd"]]
        elif nid == "fn_force_manual_and_set":
            func = n.get("func") or ""
            if "lastDashboardCmd" not in func:
                func = func.replace(
                    "return [m1, m2];",
                    "flow.set('lastDashboardCmd', t + '\\n' + m1.payload + ' ' + m2.payload);\nreturn [m1, m2];",
                )
                n["func"] = func
            n["wires"] = [["mqtt_out_cmd"]]
        elif nid == "ui_tpl_phw_water_24h":
            n["format"] = _patch_phw(n.get("format") or "")

    _ensure_cmd_preview_nodes(data)

    DASH.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print("OK patch_dashboard_user_monitor_8 (dashboard)")


def patch_mqtt() -> None:
    data = json.loads(MQTT.read_text(encoding="utf-8-sig"))
    for n in data:
        if n.get("id") != "cf_fn_ch_act":
            continue
        func = n.get("func") or ""
        needle = "const combined = cmdParts.join(' ');"
        ins = (
            needle
            + "\nflow.set('lastDashboardCmd', topic + '\\n' + combined);"
        )
        if "lastDashboardCmd" not in func and needle in func:
            n["func"] = func.replace(needle, ins, 1)
        break
    else:
        raise SystemExit("cf_fn_ch_act 없음")
    MQTT.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print("OK patch_dashboard_user_monitor_8 (mqtt)")


def merge() -> None:
    merge_py = ROOT / "scripts" / "merge_nodered_deploy.py"
    if merge_py.is_file():
        r = subprocess.run([sys.executable, str(merge_py), "--use-split"], cwd=str(ROOT))
        if r.returncode != 0:
            raise SystemExit("merge 실패")


def main() -> None:
    patch_dashboard()
    patch_mqtt()
    merge()


if __name__ == "__main__":
    main()

