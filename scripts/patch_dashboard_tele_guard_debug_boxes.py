# -*- coding: utf-8 -*-
"""
펌프 가드(tele G:): 레이아웃 조정용 노란 디버그 박스.
Bed 타임라인·Water Quality: API 실패 시 영역에 상태 코드 표시.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

GUARD_FMT = """<div class="cf-tele-guard-ui cf-fe-wide cf-arduino-stack-gap0 cf-debug-guard-root">
  <div class="cf-debug-box cf-debug-guard-title" data-cf-unit="guard-title">
    <span class="cf-debug-lbl">[1] 제목</span>
    <div class="cf-ar-title-nogap">펌프 가드</div>
  </div>
  <div class="cf-debug-box cf-debug-guard-tag" data-cf-unit="guard-tag">
    <span class="cf-debug-lbl">[2] tele G: 라벨</span>
    <div class="cf-muted">(tele G:)</div>
  </div>
  <div class="cf-debug-box cf-debug-guard-body" data-cf-unit="guard-pre">
    <span class="cf-debug-lbl">[3] G: payload</span>
    <pre class="cf-tele-guard-pre" ng-class="{'cf-guard-warn': (msg.payload||'').toString().indexOf('mx')>=0 || (msg.payload||'').toString().indexOf('mf')>=0, 'cf-guard-ok': (msg.payload||'').toString()==='ok', 'cf-guard-legacy': (msg.payload||'').toString().indexOf('—')===0}" ng-bind="msg.payload"></pre>
  </div>
</div>
<style>
.cf-debug-guard-root{display:flex;flex-direction:column;gap:4px;width:100%!important;max-width:100%!important;box-sizing:border-box;margin:0;padding:0}
.cf-debug-box{position:relative;box-sizing:border-box;outline:2px dashed #ffd60a;background:rgba(255,214,10,.07);border-radius:6px}
.cf-debug-lbl{position:absolute;top:-1px;left:6px;z-index:2;font-size:9px;font-weight:700;line-height:1.2;color:#1a1200;background:#ffd60a;padding:1px 5px;border-radius:3px;pointer-events:none}
.cf-debug-guard-title{padding:16px 8px 6px!important;min-height:26px}
.cf-debug-guard-tag{padding:14px 8px 6px!important;min-height:22px}
.cf-debug-guard-body{padding:16px 8px 8px!important;margin-top:0!important}
.cf-tele-guard-ui .cf-ar-title-nogap{margin:0!important;padding:0!important;line-height:1.15!important;font-size:12px;font-weight:600;color:var(--cf-text,#e6edf7)}
.cf-debug-guard-tag .cf-muted{margin:0;padding:0;line-height:1.15!important;font-size:11px;color:var(--cf-muted,#9db0cc)}
.cf-tele-guard-pre{display:block;margin:0!important;padding:4px 8px!important;width:100%!important;min-width:0;box-sizing:border-box!important;font-size:11.5px;line-height:1.3;color:#e6edf7;white-space:pre-wrap;word-break:break-word;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.14);border-radius:6px;min-height:1.2em;max-height:3.2em;overflow:auto}
.cf-guard-ok{border-color:rgba(40,167,69,.5)!important;background:rgba(40,167,69,.08)!important}
.cf-guard-warn{border-color:rgba(255,193,7,.6)!important;background:rgba(255,193,7,.1)!important}
.cf-guard-legacy{border-color:rgba(157,176,204,.35)!important;background:rgba(255,255,255,.04)!important}
.cf-chart-err{display:flex;align-items:center;justify-content:center;min-height:48px;padding:8px;font-size:11px;color:#ffb74d;background:rgba(255,183,77,.12);border:1px dashed #ffb74d;border-radius:8px;box-sizing:border-box}
</style>"""

CHART_ERR_SNIPPET = """      if (!r.ok) {
        var err = 'API ' + r.status;
        document.querySelectorAll('.cf-bed-hist-cwrap').forEach(function(el) {
          el.innerHTML = '<div class="cf-chart-err">' + err + '</div>';
        });
        return;
      }"""

OLD_LOAD_FAIL = "      if (!r.ok) return;"
PHW_ERR_OLD = "if(!r.ok){setMsg('API '+r.status);return;}"


def patch_guard(data: list) -> bool:
    for n in data:
        if n.get("id") == "ui_tpl_tele_guard":
            n["format"] = GUARD_FMT
            return True
    return False


def patch_hist_stacks(data: list) -> int:
    count = 0
    for node in data:
        if not (node.get("id") or "").startswith("ui_tpl_hist_stack_"):
            continue
        fmt = node.get("format") or ""
        if OLD_LOAD_FAIL in fmt:
            fmt = fmt.replace(OLD_LOAD_FAIL, CHART_ERR_SNIPPET, 1)
            count += 1
        node["format"] = fmt
    return count


def patch_phw_water(data: list) -> bool:
    for n in data:
        if n.get("id") != "ui_tpl_phw_water_24h":
            continue
        fmt = n.get("format") or ""
        if PHW_ERR_OLD in fmt:
            fmt = fmt.replace(
                PHW_ERR_OLD,
                "if(!r.ok){setMsg('API '+r.status);var el=document.getElementById('cf_phw_chart');if(el){el.innerHTML='<div class=\"cf-chart-err\">API '+r.status+'</div>';}return;}",
            )
        n["format"] = fmt
        return True
    return False


def main() -> None:
    data = json.loads(DASH.read_text(encoding="utf-8-sig"))
    if not patch_guard(data):
        raise SystemExit("ui_tpl_tele_guard 없음")
    hist_n = patch_hist_stacks(data)
    phw = patch_phw_water(data)
    DASH.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"OK tele_guard debug boxes, hist_stacks={hist_n}, phw={phw}")

    merge = ROOT / "scripts" / "merge_nodered_deploy.py"
    if merge.is_file():
        r = subprocess.run([sys.executable, str(merge), "--use-split"], cwd=str(ROOT))
        if r.returncode != 0:
            raise SystemExit("merge 실패")


if __name__ == "__main__":
    main()
