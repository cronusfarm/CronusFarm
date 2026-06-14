# -*- coding: utf-8 -*-
"""대시보드 AI 카메라: 브라우저는 항상 nginx /farm/hailo-mjpeg (localhost만 :8080 직연결). inject_cf_ai_mjpeg_boot 제거."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

REMOVE_INJECT_IDS = frozenset({"inject_cf_ai_mjpeg_boot"})
STREAM_ID = "nr_node_ui_ai_stream"

CAM_CLICK_JS = r"""
  function cfDetectApi(){
    var o=location.origin||"";
    return o+"/farm/hailo-mjpeg/detect_now";
  }
  function cfRedetect(){
    var cap=document.getElementById("cf-ai-cap-txt");
    if(cap) cap.textContent="검출 중… (클릭)";
    fetch(cfDetectApi(),{method:"POST",credentials:"same-origin"})
      .then(function(r){return r.json();})
      .then(function(j){
        if(j&&j.caption) setCap(j);
        else if(cap) cap.textContent=(j&&j.ok)?"검출 완료":"검출 결과 없음";
      })
      .catch(function(){ if(cap) cap.textContent="검출 요청 실패"; });
  }
  var stage=document.querySelector(".cf-ai-cam-stage");
  if(stage){
    stage.style.cursor="pointer";
    stage.title="화면 클릭 → 다시 검출";
    stage.addEventListener("click", function(ev){
      if(ev.target&&ev.target.id==="cf-ai-mjpeg-img") cfRedetect();
    });
  }
"""

FMT = r"""<div class="cf-ai-cam-outer">
  <div class="cf-ai-cam-stage">
    <img id="cf-ai-mjpeg-img" alt="AI camera" src="/farm/hailo-mjpeg/video_feed"/>
  </div>
  <div id="cf-ai-cap-txt" class="cf-ai-cam-caption">실시간 온실 영상 (로딩) · 화면 클릭 시 재검출</div>
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
  function apply(){
    el.src=cfCamSrc();
  }
  apply();
  var errN=0;
  el.onerror=function(){
    errN++;
    var u=el.src||"";
    if(errN===1&&u.indexOf("hailo-mjpeg")>=0){
      el.src=(location.origin||"")+CF_CAM_FALLBACK;
      el.style.transform="scaleY(-1)";
      return;
    }
    if(errN<6) setTimeout(apply, 1500*errN);
  };
""" + CAM_CLICK_JS + r"""
})(scope);
</script>"""


def main() -> None:
    d = json.loads(DASH.read_text(encoding="utf-8-sig"))
    d = [n for n in d if isinstance(n, dict) and n.get("id") not in REMOVE_INJECT_IDS]
    for n in d:
        if n.get("id") != STREAM_ID:
            continue
        n["format"] = FMT
        n["height"] = 8
        n["fwdInMessages"] = True
        n["resendOnRefresh"] = True
        break
    else:
        raise SystemExit(f"missing {STREAM_ID}")
    DASH.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("OK")


if __name__ == "__main__":
    main()
