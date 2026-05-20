# -*- coding: utf-8 -*-
"""대시보드 AI 카메라: 1880/1882/1884 → :8080/stream 직접, 그 외 → /farm/ai-mjpeg. inject_cf_ai_mjpeg_boot 만 제거."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

REMOVE_INJECT_IDS = frozenset({"inject_cf_ai_mjpeg_boot"})
STREAM_ID = "nr_node_ui_ai_stream"

FMT = r"""<div class="cf-ai-cam-outer">
  <div class="cf-ai-cam-root" style="width:100%;background:#050a12;text-align:center;">
    <img id="cf-ai-mjpeg-img" alt="AI camera" src="/farm/ai-mjpeg/video_feed" style="max-width:100%;width:auto;height:auto;object-fit:contain;display:block;margin:0 auto;background:#000;"/>
  </div>
  <div id="cf-ai-cap-txt" class="cf-ai-cam-caption">실시간 온실 영상 (로딩)</div>
</div>
<script type="text/javascript">
(function(scope){
  function setCap(v){
    var t=document.getElementById("cf-ai-cap-txt");
    if(!t||v==null||v==="")return;
    if(typeof v==="object"&&v!==null){
      if(v.caption!=null&&String(v.caption).trim()){ t.textContent=String(v.caption).trim(); return; }
      return;
    }
    t.textContent=String(v);
  }
  if(typeof scope!=="undefined"&&scope&&typeof scope.$watch==="function"){
    scope.$watch("msg", function(m){ if(m)setCap(m.payload); }, true);
  }
  var el=document.getElementById("cf-ai-mjpeg-img");
  if(!el)return;
  function piHost(){
    if(typeof window.cfPiHost==="function") return window.cfPiHost();
    return "ida.mango-larch.ts.net";
  }
  function cfCamSrc(){
    var h=location.hostname||"127.0.0.1";
    var pr=location.protocol||"http:";
    var p=String(location.port||"");
    if(p==="1881"||h==="127.0.0.1"||h==="localhost") return pr+"//"+piHost()+":8080/stream";
    if(p==="1880"||p==="80"||p==="") return (location.origin||"")+"/farm/ai-mjpeg/video_feed";
    if(/^(5188[0-2]|188[0-4])$/.test(p)) return pr+"//"+piHost()+":8080/stream";
    return (location.origin||"")+"/farm/ai-mjpeg/video_feed";
  }
  function apply(){ el.src=cfCamSrc(); }
  apply();
  window.addEventListener("cf-pi-host", apply);
  el.onerror=function(){ apply(); };
})(scope);
</script>"""


def main() -> None:
    d = json.loads(DASH.read_text(encoding="utf-8-sig"))
    d = [n for n in d if isinstance(n, dict) and n.get("id") not in REMOVE_INJECT_IDS]
    for n in d:
        if n.get("id") != STREAM_ID:
            continue
        n["format"] = FMT
        n["height"] = 12
        n["fwdInMessages"] = True
        n["resendOnRefresh"] = True
        break
    else:
        raise SystemExit(f"missing {STREAM_ID}")
    DASH.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("OK")


if __name__ == "__main__":
    main()
