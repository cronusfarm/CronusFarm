"""
개발환경(/ui) 문서 패널 추가 + PHW3988 최소 패치만 (devflow JSON 단일 파일).

- 수정 파일: nodered/flows_cronusfarm_devflow_flow.json 만
- PHW: IP 14.32.231.191, HIVEMQ 제거, mqtt out → Mosquitto(d6b7f6c1b2b3c4d5)
- 미사용: RAW debug, aquarium split 제거·배선 정리
- 차트/타임라인(d803759f55603ec6, dashboard hist 등) 은 건드리지 않음

사용 후: python scripts/merge_nodered_deploy.py --use-split
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEVFLOW = ROOT / "nodered" / "flows_cronusfarm_devflow_flow.json"

MOSQUITTO = "d6b7f6c1b2b3c4d5"
PUBLIC_IP = "14.32.231.191"

DROP_IDS = frozenset(
    {
        "d7013a5209d5fe9b",  # HIVEMQ
        "2c66449a4d7d4656",  # RAW DP debug
        "554c1b474239d145",  # split topics
    }
)

TUYA_ID = "8ed219bf73293e78"
FN_MAP_ID = "201f991e49bff34f"
FN_MQTT_ID = "d93926e2264775ad"
MQTT_OUT_ID = "4fd2979510810d5f"
CHART_FN_ID = "d803759f55603ec6"  # 수정 금지

DOC_TPL_ID = "ui_tpl_devflow_nodered_paths"

DOC_HTML = r"""<motion.div class="cf-df-paths" layout>
<style>
.cf-df-paths{font-family:system-ui,'Malgun Gothic',sans-serif;color:#ececec;line-height:1.55;max-width:960px;margin:0 auto;font-size:0.82rem}
.cf-df-paths h3{margin:0 0 8px;font-size:1rem;color:#aed581}
.cf-df-paths code{background:#1e1e24;padding:2px 6px;border-radius:4px;font-size:0.78rem;color:#ffcc80}
.cf-df-paths ul{margin:6px 0 12px 18px;padding:0}
.cf-df-paths li{margin:4px 0}
.cf-df-paths .pi{color:#81d4fa}
</style>
<h3>Node-RED 플로우 — 수정·배포 경로</h3>
<p><strong>로컬(PC)에서 수정하는 파일</strong> (저장소 <code>d:\WorkSpace\Study\MyCode\Cursor\CronusFarm\nodered\</code>)</p>
<ul>
<li><code>flows_cronusfarm_dashboard.json</code> — /ui 대시보드·모니터·설정</li>
<li><code>flows_cronusfarm_mqtt.json</code> — MQTT·tele·SQLite HTTP</li>
<li><code>flows_cronusfarm_devflow_flow.json</code> — 개발환경 탭·PHW3988 플로우</li>
</ul>
<p>배포 전 병합: <code>python scripts/merge_nodered_deploy.py --use-split</code> → <code>merged-deploy.json</code></p>
<p><strong>Pi 배포 후 실제 동작 파일</strong></p>
<ul>
<li class="pi">저장소 복사: <code>/home/dooly/CronusFarm/nodered/merged-deploy.json</code></li>
<li class="pi">Node-RED 실행: <code>/home/dooly/.node-red/flows.json</code></li>
</ul>
<p>배포: <code>.\scripts\deploy-cronusfarm-pi.ps1 -PiHost 192.168.60.222 -ApplyNodeRed -UseSplitFlows -SkipArduino</code></p>
</motion.div>"""


def strip_wires(wires: object, drop: set[str]) -> object:
    if not isinstance(wires, list):
        return wires
    out: list = []
    for branch in wires:
        if not isinstance(branch, list):
            out.append(branch)
            continue
        out.append([x for x in branch if isinstance(x, str) and x not in drop])
    return out


def patch_phw_nodes(by_id: dict[str, dict]) -> None:
    tuya = by_id.get(TUYA_ID)
    if isinstance(tuya, dict):
        tuya["deviceIp"] = PUBLIC_IP
        tuya["wires"] = [[FN_MAP_ID], []]

    fn_map = by_id.get(FN_MAP_ID)
    if isinstance(fn_map, dict):
        w = (fn_map.get("wires") or [[]])[0]
        # chart·pick 유지, split(554…) → mqtt JSON(d939…) 직결만
        new_w: list[str] = []
        for x in w:
            if x in DROP_IDS:
                continue
            if x == FN_MQTT_ID:
                continue
            if x not in new_w:
                new_w.append(x)
        if FN_MQTT_ID not in new_w:
            new_w.append(FN_MQTT_ID)
        fn_map["wires"] = [new_w]

    mqtt_fn = by_id.get(FN_MQTT_ID)
    if isinstance(mqtt_fn, dict):
        mqtt_fn["wires"] = [[MQTT_OUT_ID]]

    mqtt_out = by_id.get(MQTT_OUT_ID)
    if isinstance(mqtt_out, dict):
        mqtt_out["broker"] = MOSQUITTO
        # topic은 msg.topic(sf_3team/water) 유지 — 펌웨어 호환

    chart = by_id.get(CHART_FN_ID)
    if isinstance(chart, dict) and "wires" in chart:
        chart["wires"] = strip_wires(chart["wires"], DROP_IDS)


def ensure_doc_template(by_id: dict[str, dict]) -> None:
    if DOC_TPL_ID in by_id:
        n = by_id[DOC_TPL_ID]
        n["format"] = DOC_HTML
        return
  # ui_tab_devflow 그룹: 기존 devflow 템플릿과 동일 탭
    grp = None
    for n in by_id.values():
        if n.get("type") == "ui_group" and n.get("tab") == "ui_tab_devflow":
            grp = n.get("id")
            break
    if not grp:
        grp = "cf_grp_dev_hw"
    by_id[DOC_TPL_ID] = {
        "id": DOC_TPL_ID,
        "type": "ui_template",
        "z": "tab_cronus_devflow",
        "group": grp,
        "name": "Node-RED 수정·배포 경로",
        "order": 0,
        "width": "12",
        "height": "8",
        "format": DOC_HTML,
        "storeOutMessages": True,
        "fwdInMessages": True,
        "resendOnRefresh": True,
        "templateScope": "local",
        "className": "",
        "x": 400,
        "y": 80,
        "wires": [[]],
    }


def main() -> int:
    if not DEVFLOW.is_file():
        print(f"없음: {DEVFLOW}", file=sys.stderr)
        return 1

    raw: list = json.loads(DEVFLOW.read_text(encoding="utf-8-sig"))
    by_id: dict[str, dict] = {}
    for n in raw:
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        if not isinstance(nid, str):
            continue
        if nid in DROP_IDS:
            continue
        if n.get("type") == "mqtt-broker" and "hivemq" in str(n.get("broker", "")).lower():
            continue
        node = dict(n)
        if node.get("broker") in DROP_IDS:
            node["broker"] = MOSQUITTO
        if "wires" in node:
            node["wires"] = strip_wires(node["wires"], DROP_IDS)
        by_id[nid] = node

    patch_phw_nodes(by_id)
    ensure_doc_template(by_id)

    out = list(by_id.values())
    DEVFLOW.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"OK {DEVFLOW.name} nodes={len(out)} (PHW minimal + devflow paths panel)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
