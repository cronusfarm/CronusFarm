# -*- coding: utf-8 -*-
"""flows_cronusfarm_mqtt.json: 감사 로그 GET 프록시 + channel-action 로그 source 필드."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MQTT = ROOT / "nodered" / "flows_cronusfarm_mqtt.json"


def main() -> None:
    d = json.loads(MQTT.read_text(encoding="utf-8-sig"))
    z = "b1c5a1f1d7a2a3a1"
    for n in d:
        if n.get("id") == "cf_fn_ch_act":
            f = n["func"]
            if "source: 'ui'" not in f:
                f = f.replace("const log = {", "const log = {\n  source: 'ui',")
            old = """payload: JSON.stringify({
      device_id: devId,
      channel_key: ch,
      action: 'revert_auto',"""
            new = """payload: JSON.stringify({
      source: 'system',
      device_id: devId,
      channel_key: ch,
      action: 'revert_auto',"""
            if old in f:
                f = f.replace(old, new, 1)
            n["func"] = f
            break
    ids = {n.get("id") for n in d}
    if "cf_hin_audit" not in ids:
        d.extend(
            [
                {
                    "id": "cf_hin_audit",
                    "type": "http in",
                    "z": z,
                    "name": "audit_log GET",
                    "url": "/farm/cronusfarm-sqlite/api/audit_log",
                    "method": "get",
                    "upload": False,
                    "swaggerDoc": "",
                    "x": 190,
                    "y": 800,
                    "wires": [["cf_fn_audit"]],
                },
                {
                    "id": "cf_fn_audit",
                    "type": "function",
                    "z": z,
                    "name": "proxy audit_log",
                    "func": (
                        "const base = (env.get('CRONUSFARM_SQLITE_BRIDGE_URL') || "
                        "'http://127.0.0.1:18766').toString().replace(/\\/$/, '');\n"
                        "const u = (msg.req && msg.req.url) ? msg.req.url : '';\n"
                        "const q = u.indexOf('?') >= 0 ? u.slice(u.indexOf('?')) : '';\n"
                        "msg.method = 'GET';\n"
                        "msg.url = base + '/api/audit_log' + q;\n"
                        "return msg;"
                    ),
                    "outputs": 1,
                    "timeout": 0,
                    "noerr": 0,
                    "initialize": "",
                    "finalize": "",
                    "libs": [],
                    "x": 440,
                    "y": 800,
                    "wires": [["cf_hreq_audit"]],
                },
                {
                    "id": "cf_hreq_audit",
                    "type": "http request",
                    "z": z,
                    "name": "bridge audit_log",
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
                    "y": 800,
                    "wires": [["cf_hres_audit"]],
                },
                {
                    "id": "cf_hres_audit",
                    "type": "http response",
                    "z": z,
                    "name": "audit_log res",
                    "statusCode": "",
                    "headers": {},
                    "x": 930,
                    "y": 800,
                    "wires": [],
                },
            ]
        )
    MQTT.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("OK mqtt audit proxy")


if __name__ == "__main__":
    main()
