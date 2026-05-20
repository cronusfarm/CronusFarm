# -*- coding: utf-8 -*-
"""Arduino 카드: R4 status retain(2줄) + R4 MQTT(3줄) → 단일 위젯으로 통합."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
REMOVE_ID = "ui_txt_status_raw"

FMT_R4_MQTT = r"""<div class="cf-r4-mqtt-unified">
  <div class="cf-mqtt-unified-bar">
    <div class="cf-r4-mqtt-title">R4 MQTT</div>
    <div class="cf-dot" ng-class="msg.connLineOk ? 'cf-dot-on' : 'cf-dot-off'"></div>
    <span class="cf-mqtt-st">{{ msg.statusRetain || '—' }}</span>
    <span class="cf-mqtt-hint">retain · …/status · 점=녹색=online · Mosquitto</span>
  </div>
  <pre class="cf-mqtt-unified-raw" ng-if="msg.statusRetain && msg.statusRetain.length > 0 && msg.statusRetain.toLowerCase() !== 'online' && msg.statusRetain.toLowerCase() !== 'offline'">{{msg.statusRetain}}</pre>
</div>
<style>
.cf-r4-mqtt-unified{margin:0;padding:0;display:flex;flex-direction:column;gap:2px;width:100%}
.cf-r4-mqtt-unified .cf-mqtt-unified-bar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:6px 10px;background:rgba(79,140,255,.08);border:1px solid rgba(79,140,255,.22);border-radius:10px}
.cf-r4-mqtt-unified .cf-r4-mqtt-title{font-size:13px;font-weight:700;color:var(--cf-text,#e6edf7);margin-right:2px}
.cf-r4-mqtt-unified .cf-mqtt-st{font-size:13px;font-weight:800;color:var(--cf-text,#e6edf7)}
.cf-r4-mqtt-unified .cf-mqtt-hint{margin-left:auto;font-size:10px;color:var(--cf-muted,#9db0cc);opacity:.85}
.cf-r4-mqtt-unified .cf-mqtt-unified-raw{margin:0!important;padding:4px 8px!important;font-size:10.5px;line-height:1.35;color:#e6edf7;white-space:pre-wrap;word-break:break-word;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:8px}
</style>"""


def patch() -> None:
    data = json.loads(DASH.read_text(encoding="utf-8-sig"))
    found_merge = False
    found_calc = False
    new_data = []
    for n in data:
        if not isinstance(n, dict):
            new_data.append(n)
            continue
        nid = n.get("id")
        if nid == REMOVE_ID:
            continue
        if nid == "ui_tpl_status_line":
            n["name"] = "R4 MQTT (retain)"
            n["format"] = FMT_R4_MQTT
            found_merge = True
        elif nid == "fn_calc_online":
            n["wires"] = [["ui_tpl_conn_line", "ui_tpl_status_line"]]
            found_calc = True
        new_data.append(n)

    if not found_merge or not found_calc:
        raise SystemExit("ui_tpl_status_line 또는 fn_calc_online 없음")

    DASH.write_text(
        json.dumps(new_data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print("OK patch_dashboard_r4_mqtt_merge (removed", REMOVE_ID + ")")

    merge = ROOT / "scripts" / "merge_nodered_deploy.py"
    if merge.is_file():
        r = subprocess.run([sys.executable, str(merge), "--use-split"], cwd=str(ROOT))
        if r.returncode != 0:
            raise SystemExit("merge 실패")


if __name__ == "__main__":
    patch()
