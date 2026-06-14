# -*- coding: utf-8 -*-
"""USB 시리얼 primary: Dashboard·MQTT 플로우의 R4 tele/status MQTT 구독 비활성 + bridge HTTP 폴링."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
MQTT = ROOT / "nodered" / "flows_cronusfarm_mqtt.json"

# MQTT 구독 유지(WiFi tele) + USB HTTP 폴링 병행 (구독만 끄지 않음)
DASH_DISABLE_IDS: frozenset[str] = frozenset()
MQTT_DISABLE_IDS: frozenset[str] = frozenset()

INJECT_TELE = "inj_poll_tele_usb"
HTTP_TELE = "http_poll_tele_usb"
FN_TELE_USB = "fn_poll_tele_usb"
INJECT_STATUS = "inj_poll_status_usb"
HTTP_STATUS = "http_poll_status_usb"
FN_STATUS_USB = "fn_poll_status_usb"
FN_SEEN_TELE = "fn_seen_tele"
FN_SEEN_STATUS = "fn_seen_status"

FN_POLL_TELE_CODE = r"""const j = msg.payload || {};
const raw = (j.raw != null) ? String(j.raw) : '';
if (!raw) return null;
msg.payload = raw;
msg._via = j.via || 'usb-bridge';
msg.via = msg._via;
return msg;"""

FN_POLL_STATUS_CODE = r"""const j = msg.payload || {};
const st = (j.state != null) ? String(j.state).trim() : '';
if (!st) return null;
msg.payload = st;
return msg;"""


def _ensure_usb_poll_nodes(by: dict, tab: str) -> None:
    bridge = "http://127.0.0.1:18766"
    if INJECT_TELE not in by:
        by[INJECT_TELE] = {
            "id": INJECT_TELE,
            "type": "inject",
            "z": tab,
            "name": "tele USB poll 2s",
            "props": [{"p": "payload"}, {"p": "topic", "vt": "str"}],
            "repeat": "2",
            "crontab": "",
            "once": False,
            "onceDelay": 0.1,
            "topic": "",
            "payload": "",
            "payloadType": "date",
            "x": 120,
            "y": 120,
            "wires": [[HTTP_TELE]],
        }
    else:
        by[INJECT_TELE]["repeat"] = "2"
        by[INJECT_TELE]["wires"] = [[HTTP_TELE]]

    if HTTP_TELE not in by:
        by[HTTP_TELE] = {
            "id": HTTP_TELE,
            "type": "http request",
            "z": tab,
            "name": "GET tele/last (bridge)",
            "method": "GET",
            "ret": "obj",
            "paytoqs": "ignore",
            "url": f"{bridge}/api/tele/last?device_id=cronusfarm-01",
            "tls": "",
            "persist": False,
            "proxy": "",
            "insecureHTTPParser": False,
            "authType": "",
            "senderr": False,
            "headers": [],
            "x": 320,
            "y": 120,
            "wires": [[FN_TELE_USB]],
        }

    by[FN_TELE_USB] = {
        "id": FN_TELE_USB,
        "type": "function",
        "z": tab,
        "name": "tele JSON → raw",
        "func": FN_POLL_TELE_CODE,
        "outputs": 1,
        "timeout": 0,
        "noerr": 0,
        "initialize": "",
        "finalize": "",
        "libs": [],
        "x": 520,
        "y": 120,
        "wires": [[FN_SEEN_TELE]],
    }

    if INJECT_STATUS not in by:
        by[INJECT_STATUS] = {
            "id": INJECT_STATUS,
            "type": "inject",
            "z": tab,
            "name": "status USB poll 5s",
            "props": [{"p": "payload"}, {"p": "topic", "vt": "str"}],
            "repeat": "5",
            "crontab": "",
            "once": False,
            "onceDelay": 0.2,
            "topic": "",
            "payload": "",
            "payloadType": "date",
            "x": 120,
            "y": 180,
            "wires": [[HTTP_STATUS]],
        }
    else:
        by[INJECT_STATUS]["repeat"] = "5"
        by[INJECT_STATUS]["wires"] = [[HTTP_STATUS]]

    if HTTP_STATUS not in by:
        by[HTTP_STATUS] = {
            "id": HTTP_STATUS,
            "type": "http request",
            "z": tab,
            "name": "GET status/last (bridge)",
            "method": "GET",
            "ret": "obj",
            "paytoqs": "ignore",
            "url": f"{bridge}/api/status/last?device_id=cronusfarm-01",
            "tls": "",
            "persist": False,
            "proxy": "",
            "insecureHTTPParser": False,
            "authType": "",
            "senderr": False,
            "headers": [],
            "x": 320,
            "y": 180,
            "wires": [[FN_STATUS_USB]],
        }

    by[FN_STATUS_USB] = {
        "id": FN_STATUS_USB,
        "type": "function",
        "z": tab,
        "name": "status JSON → payload",
        "func": FN_POLL_STATUS_CODE,
        "outputs": 1,
        "timeout": 0,
        "noerr": 0,
        "initialize": "",
        "finalize": "",
        "libs": [],
        "x": 520,
        "y": 180,
        "wires": [[FN_SEEN_STATUS]] if FN_SEEN_STATUS in by else [[]],
    }


def _patch_flow(path: Path, disable_ids: frozenset[str], add_usb_poll: bool) -> None:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    by = {n["id"]: n for n in data if isinstance(n, dict) and n.get("id")}
    tab = "tab_cronus_dash" if path == DASH else "b1c5a1f1d7a2a3a1"
    for nid in ("mqtt_in_tele", "mqtt_in_status", "d1e4c46e7a9c11a1"):
        n = by.get(nid)
        if isinstance(n, dict):
            n["disabled"] = False
    for nid in disable_ids:
        n = by.get(nid)
        if isinstance(n, dict):
            n["disabled"] = True
    if add_usb_poll and path == DASH:
        _ensure_usb_poll_nodes(by, tab)
    path.write_text(json.dumps(list(by.values()), ensure_ascii=False), encoding="utf-8")


def main() -> int:
    _patch_flow(DASH, DASH_DISABLE_IDS, add_usb_poll=True)
    _patch_flow(MQTT, MQTT_DISABLE_IDS, add_usb_poll=False)
    print("OK patch_dashboard_usb_primary: MQTT on + bridge HTTP poll")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
