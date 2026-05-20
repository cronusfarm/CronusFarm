# -*- coding: utf-8 -*-
"""Arduino 카드: R4 연결·R4 MQTT 행 레이아웃·다크 테마 통일."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

FMT_CONN = r"""<div class="cf-r4-status-bar cf-arduino-conn-tile">
  <div class="cf-label">R4 연결</div>
  <div class="cf-r4-status-right">
    <div class="cf-dot" ng-class="msg.connLineOk ? 'cf-dot-on' : 'cf-dot-off'"></div>
    <span class="cf-r4-st">{{msg.connLineOk ? 'online' : 'offline'}}</span>
    <span class="cf-muted">· tele {{msg.teleAge}}s · status 수신 {{msg.statusAge}}s</span>
  </div>
</div>
<p class="cf-led-hint">내장 매트릭스: 위 = WiFi · 아래 = MQTT (메인 R4)</p>
<style>
.cf-r4-status-bar{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;padding:6px 10px;background:rgba(79,140,255,.08);border:1px solid rgba(79,140,255,.22);border-radius:10px;color:var(--cf-text,#e6edf7);width:100%;box-sizing:border-box}
.cf-r4-status-bar .cf-label{font-size:13px;font-weight:700;color:var(--cf-text,#e6edf7);margin:0}
.cf-r4-status-right{display:flex;align-items:center;gap:8px;flex-shrink:0;white-space:nowrap;font-size:12px;color:var(--cf-text,#e6edf7)}
.cf-r4-st{font-weight:700}
.cf-arduino-conn-tile{margin:0;padding:0;line-height:1.25}
.cf-led-hint{margin:4px 0 0;padding:0;font-size:10px;line-height:1.3;color:var(--cf-muted,#9db0cc);opacity:.92}
.nr-dashboard-theme .nr-dashboard-template:has(.cf-r4-status-bar) md-card,
.nr-dashboard-theme .nr-dashboard-template:has(.cf-r4-status-bar) md-card-content{background:transparent!important;color:var(--cf-text,#e6edf7)!important}
</style>"""

FMT_MQTT = r"""<div class="cf-r4-status-bar cf-r4-mqtt-tile">
  <div class="cf-label">R4 MQTT</div>
  <div class="cf-r4-status-right">
    <span class="cf-r4-retain">{{ msg.statusRetain || '—' }}</span>
    <div class="cf-dot" ng-class="msg.connLineOk ? 'cf-dot-on' : 'cf-dot-off'"></div>
    <span class="cf-r4-st">{{msg.connLineOk ? 'online' : 'offline'}}</span>
  </div>
</div>
<p class="cf-r4-hint cf-muted">retain · …/status · Mosquitto</p>
<pre class="cf-mqtt-unified-raw" ng-if="msg.statusRetain && msg.statusRetain.length > 0 && msg.statusRetain.toLowerCase() !== 'online' && msg.statusRetain.toLowerCase() !== 'offline'">{{msg.statusRetain}}</pre>
<style>
.cf-r4-mqtt-tile{margin:0;padding:0}
.cf-r4-retain{font-size:12px;font-weight:600;color:var(--cf-accent,#4f8cff)}
.cf-r4-hint{margin:4px 0 0;font-size:10px;line-height:1.3}
.cf-mqtt-unified-raw{margin:4px 0 0!important;padding:4px 8px!important;font-size:10.5px;line-height:1.35;color:#e6edf7;white-space:pre-wrap;word-break:break-word;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:8px}
</style>"""


def patch() -> None:
    data = json.loads(DASH.read_text(encoding="utf-8-sig"))
    found = set()
    for n in data:
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        if nid == "ui_tpl_conn_line":
            n["format"] = FMT_CONN
            found.add(nid)
        elif nid == "ui_tpl_status_line":
            n["format"] = FMT_MQTT
            found.add(nid)
    if found != {"ui_tpl_conn_line", "ui_tpl_status_line"}:
        raise SystemExit(f"대상 노드 누락: {found}")
    DASH.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print("OK patch_dashboard_r4_ui_styles")
    merge = ROOT / "scripts" / "merge_nodered_deploy.py"
    if merge.is_file():
        r = subprocess.run([sys.executable, str(merge), "--use-split"], cwd=str(ROOT))
        if r.returncode != 0:
            raise SystemExit("merge 실패")


if __name__ == "__main__":
    patch()
