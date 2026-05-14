#!/usr/bin/env python3
"""ui_tpl_shell_html: CROP 탭 CCTV 이미지 + 사이드바(그룹탭) KST 시각 — flows JSON 패치"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATHS = [
    ROOT / "nodered" / "flows_cronusfarm_dashboard.json",
    ROOT / "nodered" / "flows_pi_editor_latest.json",
    ROOT / "nodered" / "merged-deploy.json",
]

OLD_CSS = (
    "#cf-shell .nb-lbl{font-family:var(--fm);font-size:7px;letter-spacing:.05em;line-height:1}\n"
    "#cf-shell .ndiv{"
)
NEW_CSS = (
    "#cf-shell .nb-lbl{font-family:var(--fm);font-size:7px;letter-spacing:.05em;line-height:1}\n"
    "#cf-shell .sb-clock-wrap{align-self:stretch;margin-top:auto;width:100%;padding:8px 4px 10px;border-top:1px solid var(--border)}\n"
    "#cf-shell .sb-clock{font-family:var(--fm);font-size:7px;line-height:1.45;color:var(--text2);text-align:center}\n"
    "#cf-shell .sb-clock b{color:var(--accent);font-weight:600;font-size:8px;letter-spacing:.02em;display:block}\n"
    "#cf-shell .ndiv{"
)

OLD_NAV = (
    "    <div class=\"nb\" data-dash=\"alrt\"><div class=\"nb-ic\">△</div><div class=\"nb-lbl\">ALRT</div></div>\n"
    "  </nav>"
)
NEW_NAV = (
    "    <div class=\"nb\" data-dash=\"alrt\"><div class=\"nb-ic\">△</div><div class=\"nb-lbl\">ALRT</div></div>\n"
    "    <div class=\"sb-clock-wrap\"><div class=\"sb-clock\" id=\"cf-sidebar-clock\"></div></div>\n"
    "  </nav>"
)

OLD_CROP = (
    "<div class=\"dash\" id=\"dash-crop\"><div class=\"sec\"><div class=\"secline\"></div><div class=\"sectl\">작물·AI</div>"
    "<div class=\"secbdg\">placeholder</div><div class=\"secline\"></div></div>"
    "<div class=\"card\"><div class=\"sublbl\">(추후: 카메라/AI)</div></div></div>"
)
NEW_CROP = (
    "<div class=\"dash\" id=\"dash-crop\"><div class=\"sec\"><div class=\"secline\"></div><div class=\"sectl\">작물·AI</div>"
    "<div class=\"secbdg\">CCTV cam01</div><div class=\"secline\"></div></div>"
    "<div class=\"card\" style=\"padding:0;overflow:hidden\">"
    "<div class=\"clbl\" style=\"margin:0;padding:10px 13px 6px\">CCTV 스냅샷 <span class=\"ctype\">jpeg</span></div>"
    "<div style=\"min-height:120px;background:rgba(0,0,0,.3);display:flex;align-items:center;justify-content:center\">"
    "<img id=\"cf-cctv-img\" alt=\"cam01\" decoding=\"async\" style=\"max-width:100%;max-height:320px;width:auto;height:auto;object-fit:contain\"/>"
    "</div>"
    "<div class=\"sublbl\" style=\"padding:8px 13px 10px\">/cctv/cam01/latest.jpg (30초마다 갱신)</div></div></div>"
)

OLD_SCRIPT = """<script>
(function(){
  function pad(n){return String(n).padStart(2,'0');}
  function tick(){
    var d=new Date();
    var el=document.querySelector('#cf-shell #clock');
    if(!el) return;
    el.innerHTML = '<span>'+pad(d.getHours())+':'+pad(d.getMinutes())+':'+pad(d.getSeconds())+'</span>&nbsp; '+d.getFullYear()+'.'+pad(d.getMonth()+1)+'.'+pad(d.getDate());
  }
  tick(); setInterval(tick,1000);

  function showDash(id){
    document.querySelectorAll('#cf-shell .dash').forEach(function(d){d.classList.remove('on'); d.style.display='none';});
    var t=document.querySelector('#cf-shell #dash-'+id);
    if(t){ t.classList.add('on'); t.style.display='block'; }
    document.querySelectorAll('#cf-shell .nb').forEach(function(b){b.classList.remove('on');});
    var nb=document.querySelector('#cf-shell .nb[data-dash="'+id+'"]');
    if(nb) nb.classList.add('on');
  }
  document.querySelectorAll('#cf-shell .nb[data-dash]').forEach(function(b){
    b.addEventListener('click', function(){ showDash(this.getAttribute('data-dash')); });
  });
  showDash('main');
})();
</script>
</div>"""

MAIN_CCTV_OLD = (
    "      </div>\n\n      <div class=\"g g2\" style=\"margin-top:7px\">\n"
    "        <div class=\"card\"><div class=\"clbl\">온도·습도 24h 추이"
)
MAIN_CCTV_NEW = (
    "      </div>\n\n"
    "      <div class=\"card\" style=\"margin-top:7px;padding:0;overflow:hidden\">\n"
    "        <div class=\"clbl\" style=\"padding:10px 13px 6px\">CCTV cam01 <span class=\"ctype\">jpeg</span></div>\n"
    "        <div style=\"min-height:96px;background:rgba(0,0,0,.25);display:flex;align-items:center;justify-content:center\">\n"
    "          <img id=\"cf-cctv-img-main\" alt=\"cam01\" decoding=\"async\" "
    "style=\"max-width:100%;max-height:220px;width:auto;height:auto;object-fit:contain\"/>\n"
    "        </div>\n"
    "      </div>\n\n"
    "      <div class=\"g g2\" style=\"margin-top:7px\">\n"
    "        <div class=\"card\"><div class=\"clbl\">온도·습도 24h 추이"
)

NEW_SCRIPT = """<script>
(function(){
  function pad(n){return String(n).padStart(2,'0');}
  function fmtKst(d){
    var k=new Date(d.getTime()+9*60*60*1000);
    return k.getUTCFullYear()+'-'+pad(k.getUTCMonth()+1)+'-'+pad(k.getUTCDate())+' '+pad(k.getUTCHours())+':'+pad(k.getUTCMinutes())+':'+pad(k.getUTCSeconds())+' KST';
  }
  function tick(){
    var d=new Date();
    var el=document.querySelector('#cf-shell #clock');
    if(el) el.innerHTML = '<span>'+pad(d.getHours())+':'+pad(d.getMinutes())+':'+pad(d.getSeconds())+'</span>&nbsp; '+d.getFullYear()+'.'+pad(d.getMonth()+1)+'.'+pad(d.getDate());
    var sb=document.querySelector('#cf-shell #cf-sidebar-clock');
    if(sb) sb.innerHTML = '<b>'+fmtKst(d)+'</b>';
  }
  tick(); setInterval(tick,1000);

  function cctvBust(){
    var u = window.location.origin + '/cctv/cam01/latest.jpg?t=' + Date.now();
    ['cf-cctv-img','cf-cctv-img-main'].forEach(function(id){
      var im=document.querySelector('#cf-shell #'+id);
      if(im) im.src=u;
    });
  }
  setInterval(cctvBust, 30000);
  cctvBust();

  function showDash(id){
    document.querySelectorAll('#cf-shell .dash').forEach(function(d){d.classList.remove('on'); d.style.display='none';});
    var t=document.querySelector('#cf-shell #dash-'+id);
    if(t){ t.classList.add('on'); t.style.display='block'; }
    document.querySelectorAll('#cf-shell .nb').forEach(function(b){b.classList.remove('on');});
    var nb=document.querySelector('#cf-shell .nb[data-dash="'+id+'"]');
    if(nb) nb.classList.add('on');
    if(id==='crop'||id==='main') setTimeout(cctvBust, 80);
  }
  document.querySelectorAll('#cf-shell .nb[data-dash]').forEach(function(b){
    b.addEventListener('click', function(){ showDash(this.getAttribute('data-dash')); });
  });
  showDash('main');
})();
</script>
</div>"""

# 1차 패치만 적용된 플로우 → MAIN 미리보기 + 이중 cctvBust
OLD_SINGLE_BUST = """  function cctvBust(){
    var im=document.querySelector('#cf-shell #cf-cctv-img');
    if(!im) return;
    im.src = window.location.origin + '/cctv/cam01/latest.jpg?t=' + Date.now();
  }"""
NEW_DUAL_BUST = """  function cctvBust(){
    var u = window.location.origin + '/cctv/cam01/latest.jpg?t=' + Date.now();
    ['cf-cctv-img','cf-cctv-img-main'].forEach(function(id){
      var im=document.querySelector('#cf-shell #'+id);
      if(im) im.src=u;
    });
  }"""
OLD_SHOW_CROP = "if(id==='crop') setTimeout(cctvBust, 80);"
NEW_SHOW_MAIN = "if(id==='crop'||id==='main') setTimeout(cctvBust, 80);"


def patch_fmt(fmt: str) -> str | None:
    if "cf-cctv-img-main" in fmt:
        return None
    if "cf-sidebar-clock" in fmt and "cf-cctv-img" in fmt:
        if MAIN_CCTV_OLD not in fmt:
            raise SystemExit("v2: missing MAIN_CCTV_OLD anchor")
        fmt = fmt.replace(MAIN_CCTV_OLD, MAIN_CCTV_NEW, 1)
        if OLD_SINGLE_BUST not in fmt:
            raise SystemExit("v2: missing single-image cctvBust()")
        fmt = fmt.replace(OLD_SINGLE_BUST, NEW_DUAL_BUST, 1)
        if OLD_SHOW_CROP not in fmt:
            raise SystemExit("v2: missing showDash crop-only line")
        fmt = fmt.replace(OLD_SHOW_CROP, NEW_SHOW_MAIN, 1)
        return fmt
    for old, new in (
        (OLD_CSS, NEW_CSS),
        (OLD_NAV, NEW_NAV),
        (OLD_CROP, NEW_CROP),
        (OLD_SCRIPT, NEW_SCRIPT),
    ):
        if old not in fmt:
            raise SystemExit(f"missing fragment in format: {old[:60]}...")
        fmt = fmt.replace(old, new, 1)
    if MAIN_CCTV_OLD not in fmt:
        raise SystemExit("missing MAIN_CCTV_OLD")
    fmt = fmt.replace(MAIN_CCTV_OLD, MAIN_CCTV_NEW, 1)
    return fmt


def main() -> None:
    for path in PATHS:
        data = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for node in data:
            if node.get("id") != "ui_tpl_shell_html":
                continue
            fmt = node.get("format") or ""
            new_fmt = patch_fmt(fmt)
            if new_fmt is None:
                print(f"skip (already patched): {path.name}")
                break
            node["format"] = new_fmt
            changed = True
            break
        else:
            print(f"WARN: ui_tpl_shell_html not found: {path}")
            continue
        if changed:
            if path.name == "flows_cronusfarm_dashboard.json" or path.name == "merged-deploy.json":
                path.write_text(
                    json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8",
                )
            else:
                path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
            print(f"patched: {path}")


if __name__ == "__main__":
    main()
