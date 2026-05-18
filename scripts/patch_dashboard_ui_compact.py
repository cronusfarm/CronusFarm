# -*- coding: utf-8 -*-
"""모니터: 펌프가드 한줄·매트릭스 hint·tele 간격/겹침 수정."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

FMT_TELE_GUARD = """<div class="cf-tele-guard-ui cf-fe-wide cf-arduino-stack-gap0">
  <div class="cf-tele-guard-line">
    <span class="cf-ar-title-nogap">펌프 가드</span>
    <span class="cf-muted">(tele G:)</span>
    <span class="cf-tele-guard-val" ng-class="{'cf-guard-warn': (msg.payload||'').toString().indexOf('mx')>=0 || (msg.payload||'').toString().indexOf('mf')>=0, 'cf-guard-ok': (msg.payload||'').toString()==='ok', 'cf-guard-legacy': (msg.payload||'').toString().indexOf('—')===0}" ng-bind="msg.payload"></span>
  </div>
</div>
<style>
.cf-tele-guard-ui{margin:0 0 2px!important;padding:0!important;width:100%!important;box-sizing:border-box}
.cf-tele-guard-line{display:flex;align-items:center;gap:6px;flex-wrap:wrap;line-height:1.25;font-size:12px}
.cf-tele-guard-ui .cf-ar-title-nogap{margin:0!important;padding:0!important;font-size:12px;font-weight:600;color:var(--cf-text,#e6edf7)}
.cf-tele-guard-line .cf-muted{font-size:11px;color:var(--cf-muted,#9db0cc)}
.cf-tele-guard-val{font-size:11.5px;font-weight:700;color:#e6edf7;padding:1px 6px;border-radius:4px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.12);max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cf-guard-ok{border-color:rgba(40,167,69,.5)!important;background:rgba(40,167,69,.08)!important}
.cf-guard-warn{border-color:rgba(255,193,7,.6)!important;background:rgba(255,193,7,.1)!important}
.cf-guard-legacy{border-color:rgba(157,176,204,.35)!important;background:rgba(255,255,255,.04)!important}
.nr-dashboard-template:has(.cf-tele-guard-ui),
.nr-dashboard-template:has(.cf-tele-guard-ui) md-card{min-height:0!important;height:auto!important}
.nr-dashboard-template:has(.cf-tele-guard-ui) md-card-content{padding:4px 10px!important;min-height:0!important;height:auto!important}
</style>"""

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

FMT_TELE_SUM = """<div class="cf-tele-sum-ui"><div class="cf-ar-title-nogap">tele · 미리보기 <span class="cf-muted" style="font-weight:600;font-size:11px">(아래에 전체)</span></div><pre class="cf-tele-sum-pre">{{msg.payload}}</pre></div>
<style>
.cf-tele-sum-ui{margin:0;padding:0;display:flex;flex-direction:column;gap:2px;width:100%;min-height:0;overflow:visible!important}
.cf-tele-sum-ui .cf-ar-title-nogap{margin:0!important;padding:0!important;line-height:1.2!important;font-size:12px;color:var(--cf-muted,#9db0cc)}
.cf-tele-sum-pre{display:block;margin:0!important;padding:4px 8px!important;width:100%;box-sizing:border-box!important;font-size:10.5px;line-height:1.3;color:#e6edf7;white-space:pre-wrap;word-break:break-word;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:8px;max-height:7em!important;min-height:0!important;overflow-y:auto!important;position:relative;z-index:0}
.nr-dashboard-template:has(.cf-tele-sum-ui){height:auto!important;min-height:0!important;overflow:visible!important;margin-bottom:0!important}
.nr-dashboard-template:has(.cf-tele-sum-ui) md-card-content{padding-bottom:6px!important}
</style>"""

FMT_TELE_RAW = """<div class="cf-tele-raw-ui cf-arduino-stack-gap0"><div class="cf-ar-title-nogap">전체 tele 문자열</div><pre class="cf-tele-raw-pre">{{msg.payload}}</pre></div>
<style>
.cf-tele-raw-ui{margin:2px 0 0;padding:0;display:flex;flex-direction:column;gap:2px;width:100%;min-height:0;overflow:visible!important}
.cf-tele-raw-ui .cf-ar-title-nogap{margin:0!important;padding:0!important;line-height:1.15!important;font-size:12px;color:var(--cf-muted,#9db0cc)}
.cf-tele-raw-pre{display:block;margin:0!important;padding:4px 8px!important;width:100%;box-sizing:border-box!important;font-size:10.5px;line-height:1.35;color:#e6edf7;white-space:pre-wrap;word-break:break-word;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:8px;min-height:1.2em;max-height:min(42vh,22rem)!important;overflow-y:auto!important;position:relative;z-index:0}
.nr-dashboard-template:has(.cf-tele-raw-ui){height:auto!important;min-height:0!important;overflow:visible!important;margin-top:0!important;padding-top:0!important}
.nr-dashboard-template:has(.cf-tele-raw-ui) md-card-content{padding-top:4px!important}
</style>"""


def _fix(s: str) -> str:
    return s.replace("<motion", "<div").replace("</motion>", "</div>")


def patch() -> None:
    data = json.loads(DASH.read_text(encoding="utf-8-sig"))
    mapping = {
        "ui_tpl_tele_guard": _fix(FMT_TELE_GUARD),
        "ui_tpl_conn_line": FMT_CONN,
        "ui_tpl_arduino_led_tele": FMT_TELE_SUM,
        "ui_txt_tele_raw": FMT_TELE_RAW,
    }
    for n in data:
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        if nid in mapping:
            n["format"] = mapping[nid]
        if nid == "ui_tpl_tele_guard":
            n["height"] = 1
    DASH.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print("OK patch_dashboard_ui_compact")
    merge = ROOT / "scripts" / "merge_nodered_deploy.py"
    if merge.is_file():
        r = subprocess.run([sys.executable, str(merge), "--use-split"], cwd=str(ROOT))
        if r.returncode != 0:
            raise SystemExit("merge 실패")


if __name__ == "__main__":
    patch()
