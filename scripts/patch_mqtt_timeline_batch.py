# -*- coding: utf-8 -*-
"""MQTT 탭: /farm/.../timeline/batch → SQLite 브리지 배치 API 프록시."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MQTT = ROOT / "nodered" / "flows_cronusfarm_mqtt.json"
TAB = "b1c5a1f1d7a2a3a1"
MARK = "cf_hin_ch_tl_batch"

FN = (
    "const base = (env.get('CRONUSFARM_SQLITE_BRIDGE_URL') || 'http://127.0.0.1:18766')"
    ".toString().replace(/\\/$/, '');\n"
    "const u = (msg.req && msg.req.url) ? msg.req.url : '';\n"
    "const q = u.indexOf('?') >= 0 ? u.slice(u.indexOf('?')) : '';\n"
    "msg.method = 'GET';\n"
    "msg.url = base + '/api/channel/timeline/batch' + q;\n"
    "return msg;"
)

NODES = [
    {
        "id": "cf_hin_ch_tl_batch",
        "type": "http in",
        "z": TAB,
        "name": "채널 타임라인 batch GET",
        "url": "/farm/cronusfarm-sqlite/api/channel/timeline/batch",
        "method": "get",
        "upload": False,
        "swaggerDoc": "",
        "x": 190,
        "y": 748,
        "wires": [["cf_fn_ch_tl_batch"]],
    },
    {
        "id": "cf_fn_ch_tl_batch",
        "type": "function",
        "z": TAB,
        "name": "→ bridge timeline batch",
        "func": FN,
        "outputs": 1,
        "noerr": 0,
        "initialize": "",
        "finalize": "",
        "libs": [],
        "x": 470,
        "y": 748,
        "wires": [["cf_hreq_ch_tl_batch"]],
    },
    {
        "id": "cf_hreq_ch_tl_batch",
        "type": "http request",
        "z": TAB,
        "name": "bridge timeline batch",
        "method": "use",
        "ret": "txt",
        "paytoqs": "ignore",
        "url": "",
        "tls": "",
        "persist": False,
        "proxy": "",
        "insecureHTTPParser": False,
        "authType": "",
        "senderr": False,
        "headers": [],
        "x": 730,
        "y": 748,
        "wires": [["cf_hres_ch_tl"]],
    },
]


def main() -> None:
    data = json.loads(MQTT.read_text(encoding="utf-8-sig"))
    if any(n.get("id") == MARK for n in data):
        print("OK mqtt timeline batch (already)")
        return
    data.extend(NODES)
    MQTT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("OK mqtt timeline batch nodes added")


if __name__ == "__main__":
    main()
