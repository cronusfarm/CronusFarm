#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pi ~/.node-red/flows.json — nr_node_ui_ai_stream 카메라 URL을 nginx 동일 origin으로 고친다."""
from __future__ import annotations

import json
import sys
from pathlib import Path

STREAM_ID = "nr_node_ui_ai_stream"

FMT = r"""<div class="cf-ai-cam-outer">
  <div class="cf-ai-cam-root" style="width:100%;background:#050a12;text-align:center;">
    <img id="cf-ai-mjpeg-img" alt="AI camera" src="/farm/hailo-mjpeg/video_feed" style="max-width:100%;width:auto;height:auto;object-fit:contain;display:block;margin:0 auto;background:#000;"/>
  </div>
  <div id="cf-ai-cap-txt" class="cf-ai-cam-caption">실시간 온실 영상 (로딩)</div>
</div>
<script type="text/javascript">
(function(scope){
  function formatCropCap(v){
    if(v==null||v==="")return "";
    if(typeof v==="object"&&v!==null){
      if(v.caption!=null&&String(v.caption).trim())return String(v.caption).trim();
      var n=v.crop_name!=null?String(v.crop_name):"—";
      var c=v.crop_count!=null?String(v.crop_count):"—";
      var l=v.leaf_count!=null?String(v.leaf_count):"—";
      if(v.crop_name!=null||v.crop_count!=null||v.leaf_count!=null)
        return "작물: "+n+" | 개수: "+c+" | 잎: "+l;
    }
    return String(v);
  }
  function setCap(v){
    var t=document.getElementById("cf-ai-cap-txt");
    if(!t)return;
    var s=formatCropCap(v);
    if(s)t.textContent=s;
  }
  if(typeof scope!=="undefined"&&scope&&typeof scope.$watch==="function"){
    scope.$watch("msg", function(m){ if(m)setCap(m.payload); }, true);
  }
  var el=document.getElementById("cf-ai-mjpeg-img");
  if(!el)return;
  var CF_CAM_PATH="/farm/hailo-mjpeg/video_feed";
  var CF_CAM_FALLBACK="/farm/ai-mjpeg/video_feed";
  function cfCamSrc(){
    var h=(location.hostname||"").toLowerCase();
    var pr=location.protocol||"http:";
    if(h==="127.0.0.1"||h==="localhost") return pr+"//"+h+":8080/stream";
    return (location.origin||"")+CF_CAM_PATH;
  }
  function apply(){ el.src=cfCamSrc(); }
  apply();
  var errN=0;
  el.onerror=function(){
    errN++;
    var u=el.src||"";
    if(errN===1&&u.indexOf("hailo-mjpeg")>=0){
      el.src=(location.origin||"")+CF_CAM_FALLBACK;
      return;
    }
    if(errN<6) setTimeout(apply, 1500*errN);
  };
})(scope);
</script>"""


def main() -> None:
    flows_p = Path.home() / ".node-red" / "flows.json"
    if len(sys.argv) > 1:
        flows_p = Path(sys.argv[1]).expanduser()
    data = json.loads(flows_p.read_text(encoding="utf-8"))
    found = False
    for n in data:
        if not isinstance(n, dict) or n.get("id") != STREAM_ID:
            continue
        n["format"] = FMT
        n["height"] = 12
        n["fwdInMessages"] = True
        n["resendOnRefresh"] = True
        found = True
        break
    if not found:
        raise SystemExit(f"missing node {STREAM_ID}")
    flows_p.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print("OK", flows_p)


if __name__ == "__main__":
    main()
