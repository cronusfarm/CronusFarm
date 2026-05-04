# -*- coding: utf-8 -*-
"""flows_cronusfarm_dashboard.json 에 SQLite 브리지 HTTP 프록시(GET/PUT /farm/cronusfarm-sqlite/api/schedule) 추가."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

FN_GET = """const base = (env.get('CRONUSFARM_SQLITE_BRIDGE_URL') || 'http://127.0.0.1:18766').toString().replace(/\\/$/, '');
const u = (msg.req && msg.req.url) ? msg.req.url : '';
const q = u.indexOf('?') >= 0 ? u.slice(u.indexOf('?')) : '';
msg.method = 'GET';
msg.url = base + '/api/schedule' + q;
return msg;"""

FN_PUT = """const base = (env.get('CRONUSFARM_SQLITE_BRIDGE_URL') || 'http://127.0.0.1:18766').toString().replace(/\\/$/, '');
const u = (msg.req && msg.req.url) ? msg.req.url : '';
const q = u.indexOf('?') >= 0 ? u.slice(u.indexOf('?')) : '';
msg.method = 'PUT';
msg.url = base + '/api/schedule' + q;
msg.headers = { 'Content-Type': 'application/json; charset=utf-8' };
if (typeof msg.payload === 'object' && msg.payload !== null) {
  msg.payload = JSON.stringify(msg.payload);
} else if (typeof msg.payload === 'string') {
} else {
  msg.payload = msg.payload != null ? String(msg.payload) : '{}';
}
return msg;"""

NODES = [
    {
        "id": "cf_hin_sch_get",
        "type": "http in",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "SQLite 스케줄 GET",
        "url": "/farm/cronusfarm-sqlite/api/schedule",
        "method": "get",
        "upload": False,
        "swaggerDoc": "",
        "x": 130,
        "y": 700,
        "wires": [["cf_fn_sch_get"]],
    },
    {
        "id": "cf_fn_sch_get",
        "type": "function",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "→ bridge GET",
        "func": FN_GET,
        "outputs": 1,
        "noerr": 0,
        "initialize": "",
        "finalize": "",
        "libs": [],
        "x": 360,
        "y": 700,
        "wires": [["cf_hreq_sch"]],
    },
    {
        "id": "cf_hin_sch_put",
        "type": "http in",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "SQLite 스케줄 PUT",
        "url": "/farm/cronusfarm-sqlite/api/schedule",
        "method": "put",
        "upload": False,
        "swaggerDoc": "",
        "x": 130,
        "y": 760,
        "wires": [["cf_fn_sch_put"]],
    },
    {
        "id": "cf_fn_sch_put",
        "type": "function",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "→ bridge PUT",
        "func": FN_PUT,
        "outputs": 1,
        "noerr": 0,
        "initialize": "",
        "finalize": "",
        "libs": [],
        "x": 360,
        "y": 760,
        "wires": [["cf_hreq_sch"]],
    },
    {
        "id": "cf_hreq_sch",
        "type": "http request",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "bridge schedule",
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
        "x": 580,
        "y": 730,
        "wires": [["cf_hres_sch"]],
    },
    {
        "id": "cf_hres_sch",
        "type": "http response",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "스케줄 응답",
        "statusCode": "",
        "headers": {},
        "x": 800,
        "y": 730,
        "wires": [],
    },
]


def main() -> None:
    flows = json.loads(FLOW.read_text(encoding="utf-8"))
    ids = {n.get("id") for n in flows if isinstance(n, dict)}
    if "cf_hreq_sch" in ids:
        print("skip: proxy nodes already present")
        return
    flows.extend(NODES)
    FLOW.write_text(json.dumps(flows, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    print(f"OK appended schedule proxy to {FLOW}")


if __name__ == "__main__":
    main()
