# -*- coding: utf-8 -*-
"""append_telegram_welcome_poll.py 의 텔레그램 폴링 플로우에 '날씨(Open-Meteo)' 분기를 반영.

- cf_fn_tg_dispatch: outputs=2 (0=바로 sendMessage, 1=날씨 요청)
- 날씨 노드 3개 추가:
  - cf_fn_tg_weather_url (function, outputs=2): Open-Meteo URL 생성 / (환경변수 없으면 즉시 sendMessage)
  - cf_hreq_tg_weather (http request): Open-Meteo 호출
  - cf_fn_tg_weather_fmt (function): 예시 형태로 텍스트 구성 → sendMessage
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
APPEND = ROOT / "scripts" / "append_telegram_welcome_poll.py"


def extract(block: str, src: str) -> str:
    m = re.search(rf"{re.escape(block)}\s*=\s*r\"\"\"(.*?)\"\"\"", src, re.DOTALL)
    if not m:
        raise SystemExit(f"{block} not found in {APPEND.name}")
    return m.group(1)


def main() -> None:
    src = APPEND.read_text(encoding="utf-8")
    fn_dispatch = extract("FN_DISPATCH", src)
    fn_weather_url = extract("FN_WEATHER_URL", src)
    fn_weather_fmt = extract("FN_WEATHER_FMT", src)

    flows = json.loads(FLOW.read_text(encoding="utf-8"))
    ids = {n.get("id") for n in flows if isinstance(n, dict)}

    def upsert(node: dict) -> None:
        nid = node["id"]
        for i, n in enumerate(flows):
            if isinstance(n, dict) and n.get("id") == nid:
                flows[i] = {**n, **node}
                return
        flows.append(node)
        ids.add(nid)

    # 1) dispatch 업데이트 + wiring
    for n in flows:
        if not isinstance(n, dict):
            continue
        if n.get("id") == "cf_fn_tg_dispatch":
            n["func"] = fn_dispatch
            n["outputs"] = 2
            n["wires"] = [["cf_hreq_tg_sendmsg"], ["cf_fn_tg_weather_url"]]
            break
    else:
        raise SystemExit("cf_fn_tg_dispatch not found in flows")

    # 2) 날씨 노드 추가/업데이트
    upsert(
        {
            "id": "cf_fn_tg_weather_url",
            "type": "function",
            "z": "b1c5a1f1d7a2a3a1",
            "name": "날씨 URL(Open-Meteo)",
            "func": fn_weather_url,
            "outputs": 2,
            "noerr": 0,
            "initialize": "",
            "finalize": "",
            "libs": [],
            "x": 760,
            "y": 980,
            "wires": [["cf_hreq_tg_weather"], ["cf_hreq_tg_sendmsg"]],
        }
    )
    upsert(
        {
            "id": "cf_hreq_tg_weather",
            "type": "http request",
            "z": "b1c5a1f1d7a2a3a1",
            "name": "Open-Meteo 날씨",
            "method": "use",
            "ret": "txt",
            "paytoqs": "ignore",
            "url": "",
            "tls": "",
            "persist": False,
            "proxy": "",
            "authType": "",
            "senderr": False,
            "headers": [],
            "x": 980,
            "y": 980,
            "wires": [["cf_fn_tg_weather_fmt"]],
        }
    )
    upsert(
        {
            "id": "cf_fn_tg_weather_fmt",
            "type": "function",
            "z": "b1c5a1f1d7a2a3a1",
            "name": "날씨 메시지 포맷",
            "func": fn_weather_fmt,
            "outputs": 1,
            "noerr": 0,
            "initialize": "",
            "finalize": "",
            "libs": [],
            "x": 1190,
            "y": 980,
            "wires": [["cf_hreq_tg_sendmsg"]],
        }
    )

    # 3) inject 주기(append 기준으로 유지: 8초)
    for n in flows:
        if isinstance(n, dict) and n.get("id") == "cf_inj_tg_welcome":
            n["repeat"] = "8"
            break

    FLOW.write_text(json.dumps(flows, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    print("OK patched telegram weather flow:", FLOW)


if __name__ == "__main__":
    main()

