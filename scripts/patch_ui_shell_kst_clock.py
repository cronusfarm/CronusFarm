#!/usr/bin/env python3
"""ui_tpl_shell_html: 메뉴바·사이드바 시계 Asia/Seoul (이중 +9h 오프셋 제거)"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATHS = [
    ROOT / "nodered" / "flows_cronusfarm_dashboard.json",
    ROOT / "nodered" / "flows_pi_editor_latest.json",
    ROOT / "nodered" / "merged-deploy.json",
]

OLD_TICK = """  function fmtKst(d){
    var k=new Date(d.getTime()+9*60*60*1000);
    return k.getUTCFullYear()+'-'+pad(k.getUTCMonth()+1)+'-'+pad(k.getUTCDate())+' '+pad(k.getUTCHours())+':'+pad(k.getUTCMinutes())+':'+pad(k.getUTCSeconds())+' KST';
  }
  function tick(){
    var d=new Date();
    var el=document.querySelector('#cf-shell #clock');
    if(el) el.innerHTML = '<span>'+pad(d.getHours())+':'+pad(d.getMinutes())+':'+pad(d.getSeconds())+'</span>&nbsp; '+d.getFullYear()+'.'+pad(d.getMonth()+1)+'.'+pad(d.getDate());
    var sb=document.querySelector('#cf-shell #cf-sidebar-clock');
    if(sb) sb.innerHTML = '<b>'+fmtKst(d)+'</b>';
  }"""

NEW_TICK = """  var CF_TZ='Asia/Seoul';
  function kstParts(d){
    var o={};
    new Intl.DateTimeFormat('en-GB',{timeZone:CF_TZ,hour12:false,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'}).formatToParts(d).forEach(function(p){o[p.type]=p.value;});
    return o;
  }
  function fmtKst(d){
    var p=kstParts(d||new Date());
    return p.year+'.'+p.month+'.'+p.day+' '+p.hour+':'+p.minute+':'+p.second;
  }
  function tick(){
    var line=fmtKst(new Date());
    var sp=line.indexOf(' ');
    var date=line.slice(0,sp), time=line.slice(sp+1);
    var el=document.querySelector('#cf-shell #clock');
    if(el) el.innerHTML = '<span>'+time+'</span>&nbsp; '+date;
    var sb=document.querySelector('#cf-shell #cf-sidebar-clock');
    if(sb) sb.innerHTML = '<b>'+line+' KST</b>';
  }"""


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
            if "cf-shell" not in fmt or OLD_TICK not in fmt:
                continue
            node["format"] = fmt.replace(OLD_TICK, NEW_TICK, 1)
            changed = True
            n += 1
            print(f"patched {path.name} node {node.get('id')}")
        if changed:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK ({n} nodes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
