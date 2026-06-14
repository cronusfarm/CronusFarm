# -*- coding: utf-8 -*-
"""컨트롤박스 CSI camera0 — Arduino 그룹에서 별도 카드로 분리."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUP_ID = "ui_grp_csi_camera"
STREAM_ID = "nr_node_ui_csi_stream"
MONITOR_TAB = "ui_tab_monitor"
STREAM_HEIGHT = "6"

CSI_FMT = r"""<div class="cf-csi-cam-outer" style="position:relative!important;width:100%!important;height:100%!important;line-height:0!important;margin:0!important;padding:0!important;box-sizing:border-box!important;">
  <div class="cf-csi-cam-stage" style="position:relative!important;width:100%!important;height:100%!important;display:flex!important;align-items:center!important;justify-content:center!important;background:#050a12!important;overflow:hidden!important;">
    <img id="cf-csi-mjpeg-img" alt="컨트롤박스 camera0" style="display:block!important;width:100%!important;height:100%!important;object-fit:contain!important;background:#000!important;"/>
    <div id="cf-csi-cap-txt" style="position:absolute!important;bottom:0!important;left:0!important;right:0!important;z-index:5!important;padding:4px 8px 5px!important;font-size:12px!important;font-weight:800!important;color:#b3e5fc!important;text-align:center!important;background:linear-gradient(transparent,rgba(5,10,18,.85) 40%,rgba(5,10,18,.95))!important;pointer-events:none!important;">컨트롤박스 내부 camera0 (CSI)</div>
  </div>
</div>
<script type="text/javascript">
(function(){
  var CF_CSI="/farm/csi-mjpeg/video_feed";
  var lastRetry=0, lastFrameAt=Date.now();
  function camUrl(){
    var o=location.origin||"";
    var h=(location.hostname||"").toLowerCase();
    if(h==="127.0.0.1"||h==="localhost") return (location.protocol||"http:")+"//"+h+":8082/video_feed?t="+Date.now();
    return o+CF_CSI+(CF_CSI.indexOf("?")>=0?"&":"?")+"t="+Date.now();
  }
  function bindStream(force){
    var im=document.getElementById("cf-csi-mjpeg-img");
    if(!im) return;
    if(!force && im.getAttribute("data-cf-csi-live")==="1") return;
    im.setAttribute("data-cf-csi-live","1");
    lastFrameAt=Date.now();
    im.src=camUrl();
    im.onload=function(){ lastFrameAt=Date.now(); };
    im.onerror=function(){
      var now=Date.now();
      if(now-lastRetry<3000) return;
      lastRetry=now;
      im.removeAttribute("data-cf-csi-live");
      var cap=document.getElementById("cf-csi-cap-txt");
      if(cap) cap.textContent="CSI 영상 재연결 중…";
      bindStream(true);
    };
  }
  function maybeRecover(){
    var im=document.getElementById("cf-csi-mjpeg-img");
    if(!im||document.hidden) return;
    if(Date.now()-lastFrameAt>15000){
      im.removeAttribute("data-cf-csi-live");
      bindStream(true);
    }
  }
  bindStream(false);
  if(!window.__cfCsiCamWatch){
    window.__cfCsiCamWatch=1;
    setInterval(maybeRecover, 10000);
    document.addEventListener("visibilitychange",function(){
      if(document.visibilityState==="visible") bindStream(true);
    });
  }
})();
</script>"""

GROUP_NODE = {
    "id": GROUP_ID,
    "type": "ui_group",
    "name": "컨트롤박스 camera0 (CSI)",
    "tab": MONITOR_TAB,
    "order": 10,
    "disp": True,
    "width": "12",
    "collapse": False,
}

STREAM_NODE = {
    "id": STREAM_ID,
    "type": "ui_template",
    "z": "tab_cronus_dash",
    "group": GROUP_ID,
    "name": "컨트롤박스 camera0 (CSI)",
    "order": 1,
    "width": "12",
    "height": STREAM_HEIGHT,
    "format": CSI_FMT,
    "storeOutMessages": True,
    "fwdInMessages": False,
    "resendOnRefresh": True,
    "templateScope": "local",
    "className": "",
    "x": 400,
    "y": 720,
    "wires": [[]],
}

FLOW_FILES = [
    ROOT / "nodered" / "flows_cronusfarm_dashboard.json",
    ROOT / "nodered" / "merged-deploy.json",
    ROOT / "nodered" / "CronusFarm_NodeRED_flow.json",
]


def patch_file(path: Path) -> list[str]:
    if not path.is_file():
        return []
    flows = json.loads(path.read_text(encoding="utf-8-sig"))
    by_id = {n.get("id"): n for n in flows if isinstance(n, dict) and n.get("id")}
    changed: list[str] = []

    if GROUP_ID not in by_id:
        flows.append(dict(GROUP_NODE))
        changed.append(GROUP_ID)
    else:
        g = by_id[GROUP_ID]
        for k, v in GROUP_NODE.items():
            if g.get(k) != v:
                g[k] = v
                changed.append(GROUP_ID)

    if STREAM_ID in by_id:
        n = by_id[STREAM_ID]
        merged = dict(n)
        merged.update(STREAM_NODE)
        if merged != n:
            by_id[STREAM_ID] = merged
            changed.append(STREAM_ID)
    else:
        flows.append(dict(STREAM_NODE))
        changed.append(STREAM_ID)

    if changed:
        out = []
        seen = set()
        for n in flows:
            nid = n.get("id") if isinstance(n, dict) else None
            if nid and nid in by_id:
                if nid not in seen:
                    out.append(by_id[nid])
                    seen.add(nid)
            else:
                out.append(n)
        for nid, node in by_id.items():
            if nid not in seen and nid in {GROUP_ID, STREAM_ID}:
                out.append(node)
        path.write_text(
            json.dumps(out, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    return changed


def main() -> int:
    touched: list[str] = []
    for fp in FLOW_FILES:
        ch = patch_file(fp)
        if ch:
            touched.append(f"{fp.name}: {', '.join(ch)}")
    if not touched:
        print("WARN patch_dashboard_csi_controlbox_camera: no changes")
        return 1
    print("OK patch_dashboard_csi_controlbox_camera:", "; ".join(touched))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
