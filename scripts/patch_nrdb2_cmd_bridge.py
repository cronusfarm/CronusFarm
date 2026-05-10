# -*- coding: utf-8 -*-
"""NRDB2 제어 출력 브리지 노드 복구.

문제:
- NRDB2 ui-template(A/B/C/D Bed)에서 f1e2d3c4b5a6800f로 출력하지만
  해당 노드가 flows JSON에 누락되어 제어 명령이 MQTT로 발행되지 않음.

해결:
- 누락된 function 노드(f1e2d3c4b5a6800f) 추가
- topic/payload를 cronusfarm/<device>/cmd 문자열 2건(auto_=0, key=value)으로 변환
- mqtt_out_cmd로 전송
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

NODE_ID = "f1e2d3c4b5a6800f"
TAB = "tab_cronus_dash"

FUNC = """const devId = flow.get('deviceId') || 'cronusfarm-01';
flow.set('deviceId', devId);

const k = (msg.topic || '').toString().trim();
if (!k) return null;
const v = (msg.payload===1 || msg.payload===true || msg.payload==='1' || msg.payload==='on') ? 1 : 0;

const t = `cronusfarm/${devId}/cmd`;
// 수동 제어 시 AUTO 강제 해제 후 값 적용
const m1 = { topic: t, payload: `auto_${k}=0` };
const m2 = { topic: t, payload: `${k}=${v}` };
return [m1, m2];"""


def main() -> None:
    flows = json.loads(FLOW.read_text(encoding="utf-8"))
    ids = {n.get("id") for n in flows if isinstance(n, dict)}
    if NODE_ID in ids:
        print("skip: nrdb2 cmd bridge already exists")
        return

    flows.append(
        {
            "id": NODE_ID,
            "type": "function",
            "z": TAB,
            "name": "NRDB2: 수동고정+ON/OFF",
            "func": FUNC,
            "outputs": 1,
            "timeout": 0,
            "noerr": 0,
            "initialize": "",
            "finalize": "",
            "libs": [],
            "x": 480,
            "y": 1240,
            "wires": [["mqtt_out_cmd"]],
        }
    )

    FLOW.write_text(json.dumps(flows, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    print("OK patched NRDB2 cmd bridge:", FLOW)


if __name__ == "__main__":
    main()
