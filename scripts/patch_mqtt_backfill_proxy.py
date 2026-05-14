# -*- coding: utf-8 -*-
"""flows_cronusfarm_mqtt.json: POST /api/channel/backfill 프록시 추가."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MQTT = ROOT / "nodered" / "flows_cronusfarm_mqtt.json"

FN = """const base = (env.get('CRONUSFARM_SQLITE_BRIDGE_URL') || 'http://127.0.0.1:18766').toString().replace(/\\/$/, '');
msg.method = 'POST';
msg.url = base + '/api/channel/backfill';
msg.headers = { 'Content-Type': 'application/json; charset=utf-8' };
if (typeof msg.payload === 'object' && msg.payload !== null) {
  msg.payload = JSON.stringify(msg.payload);
} else if (typeof msg.payload === 'string') {
} else {
  msg.payload = msg.payload != null ? String(msg.payload) : '{}';
}
return msg;"""


def main() -> None:
    d = json.loads(MQTT.read_text(encoding="utf-8-sig"))
    z = "b1c5a1f1d7a2a3a1"
    ids = {n.get("id") for n in d}
    if "cf_hin_backfill" in ids:
        print("skip: already patched")
        return
    d.extend(
        [
            {
                "id": "cf_hin_backfill",
                "type": "http in",
                "z": z,
                "name": "backfill POST",
                "url": "/farm/cronusfarm-sqlite/api/channel/backfill",
                "method": "post",
                "upload": False,
                "swaggerDoc": "",
                "x": 190,
                "y": 880,
                "wires": [["cf_fn_backfill"]],
            },
            {
                "id": "cf_fn_backfill",
                "type": "function",
                "z": z,
                "name": "proxy backfill",
                "func": FN,
                "outputs": 1,
                "timeout": 0,
                "noerr": 0,
                "initialize": "",
                "finalize": "",
                "libs": [],
                "x": 440,
                "y": 880,
                "wires": [["cf_hreq_backfill"]],
            },
            {
                "id": "cf_hreq_backfill",
                "type": "http request",
                "z": z,
                "name": "bridge backfill",
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
                "x": 700,
                "y": 880,
                "wires": [["cf_hres_backfill"]],
            },
            {
                "id": "cf_hres_backfill",
                "type": "http response",
                "z": z,
                "name": "backfill res",
                "statusCode": "",
                "headers": {},
                "x": 930,
                "y": 880,
                "wires": [],
            },
        ]
    )
    MQTT.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("OK mqtt backfill POST proxy")


if __name__ == "__main__":
    main()
