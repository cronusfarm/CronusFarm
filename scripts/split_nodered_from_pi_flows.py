# -*- coding: utf-8 -*-
"""Pi ~/.node-red/flows.json(에디터 Deploy 본문)을 분할 3파일 + merged-deploy.json 으로 씁니다.

출력:
  nodered/flows_cronusfarm_mqtt.json
  nodered/flows_cronusfarm_dashboard.json
  nodered/flows_cronusfarm_devflow_flow.json
  nodered/merged-deploy.json  (merge_nodered_deploy.py --use-split 과 동일 규칙)

입력 기본: nodered/flows_pi_editor_latest.json (Pi에서 scp 한 파일)
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NR = ROOT / "nodered"
PI_FLOW = NR / "flows_pi_editor_latest.json"

MQTT_TAB = "b1c5a1f1d7a2a3a1"
DASH_TABS = frozenset({"tab_cronus_dash"})
DEVFLOW_TABS = frozenset({"tab_cronus_devflow"})


def bucket_for(n: dict) -> str:
    """mqtt | dashboard | devflow"""
    t = n.get("type")
    nid = n.get("id")
    z = n.get("z")

    if t == "tab":
        if nid == MQTT_TAB:
            return "mqtt"
        if nid in DASH_TABS:
            return "dashboard"
        return "devflow"

    if z == MQTT_TAB:
        return "mqtt"
    if z in DASH_TABS:
        return "dashboard"
    if z in DEVFLOW_TABS:
        return "devflow"
    if z:
        return "devflow"

    if t == "mqtt-broker":
        return "mqtt"
    if isinstance(t, str) and t.startswith("ui_"):
        return "dashboard"
    if t in ("global-config",):
        return "mqtt"
    if t == "subflow":
        return "devflow"
    return "devflow"


def main() -> None:
    src = PI_FLOW
    if len(sys.argv) > 1:
        src = Path(sys.argv[1])
    if not src.is_file():
        raise SystemExit(f"없음: {src} (Pi에서 scp: ~/.node-red/flows.json)")

    data = json.loads(src.read_text(encoding="utf-8-sig"))
    if not isinstance(data, list):
        raise SystemExit("flows 최상위는 배열이어야 합니다.")

    mqtt_nodes: list[dict] = []
    dash_nodes: list[dict] = []
    dev_nodes: list[dict] = []

    for n in data:
        if not isinstance(n, dict):
            continue
        b = bucket_for(n)
        if b == "mqtt":
            mqtt_nodes.append(n)
        elif b == "dashboard":
            dash_nodes.append(n)
        else:
            dev_nodes.append(n)

    (NR / "flows_cronusfarm_mqtt.json").write_text(
        json.dumps(mqtt_nodes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (NR / "flows_cronusfarm_dashboard.json").write_text(
        json.dumps(dash_nodes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (NR / "flows_cronusfarm_devflow_flow.json").write_text(
        json.dumps(dev_nodes, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "merge_nodered_deploy.py"), "--use-split"],
        cwd=str(ROOT),
    )
    if r.returncode != 0:
        raise SystemExit("merge_nodered_deploy.py 실패")

    print(
        "OK split from",
        src.name,
        "mqtt=",
        len(mqtt_nodes),
        "dashboard=",
        len(dash_nodes),
        "devflow=",
        len(dev_nodes),
    )


if __name__ == "__main__":
    main()
