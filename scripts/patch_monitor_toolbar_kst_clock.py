#!/usr/bin/env python3
"""모니터 탭 툴바 시계(cf-monitor-tab-clock): Asia/Seoul 고정 (브라우저 TZ 무관)."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATHS = [
    ROOT / "nodered" / "flows_cronusfarm_dashboard.json",
    ROOT / "nodered" / "flows_pi_editor_latest.json",
    ROOT / "nodered" / "merged-deploy.json",
]

OLD_TICK = r"""  function tick(){
    var el=document.getElementById(ID);
    if(!el) return;
    el.textContent=new Date().toLocaleString("ko-KR",{
      year:"numeric",month:"2-digit",day:"2-digit",
      hour:"2-digit",minute:"2-digit",second:"2-digit",hour12:false
    });
  }"""

NEW_TICK = r"""  var CF_TZ='Asia/Seoul';
  function fmtKstNow(){
    var p={}, d=new Date();
    new Intl.DateTimeFormat('en-GB',{timeZone:CF_TZ,hour12:false,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'}).formatToParts(d).forEach(function(x){p[x.type]=x.value;});
    return p.year+'.'+p.month+'.'+p.day+' '+p.hour+':'+p.minute+':'+p.second;
  }
  function tick(){
    var el=document.getElementById(ID);
    if(!el) return;
    el.textContent=fmtKstNow();
  }"""

# 공백/따옴표 변형(이전 패치본)
OLD_TICK_RE = re.compile(
    r"function tick\(\)\{\s*var el=document\.getElementById\(ID\);\s*if\(!el\) return;\s*"
    r"el\.textContent=new Date\(\)\.toLocaleString\([\"']ko-KR[\"'],\{[\s\S]*?hour12:false\s*\}\);\s*\}",
    re.MULTILINE,
)


def patch_format(fmt: str) -> tuple[str, bool]:
    if "cf-monitor-tab-clock" not in fmt:
        return fmt, False
    if NEW_TICK.strip() in fmt:
        return fmt, False
    if OLD_TICK in fmt:
        return fmt.replace(OLD_TICK, NEW_TICK, 1), True
    m = OLD_TICK_RE.search(fmt)
    if m:
        return fmt[: m.start()] + NEW_TICK + fmt[m.end() :], True
    return fmt, False


def main() -> int:
    n = 0
    for path in PATHS:
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for node in data:
            if node.get("type") != "ui_template":
                continue
            fmt = node.get("format") or ""
            new_fmt, did = patch_format(fmt)
            if did:
                node["format"] = new_fmt
                changed = True
                n += 1
                print(f"patched {path.name} {node.get('id')}")
        if changed:
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    print(f"OK ({n} nodes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
