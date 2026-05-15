"""
PHW3988(Tuya) → CronusFarm 모니터·MQTT·SQLite 연동 패치.

- deviceIp: 14.32.231.191 (구 192.168.60.132)
- sf_3team → cronus 토픽/이름
- HIVEMQ 브로커·RAW debug·aquarium split 제거
- fn_map → 게이지/차트 + SQLite sensor + Mosquitto cronus/water

사용: python scripts/patch_phw3988_cronus.py
      python scripts/rebuild_dashboard_split_from_pi.py
      python scripts/merge_nodered_deploy.py --use-split
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PI_PATH = ROOT / "nodered" / "flows_pi_editor_latest.json"

PHW_TAB = "02ccfe788704ab49"
DASH_Z = "tab_cronus_dash"
MOSQUITTO = "d6b7f6c1b2b3c4d5"

DROP_IDS = frozenset(
    {
        "d7013a5209d5fe9b",  # HIVEMQ broker
        "2c66449a4d7d4656",  # RAW DP debug
        "554c1b474239d145",  # aquarium split (미사용)
    }
)

FN_MAP_ID = "201f991e49bff34f"
FN_MQTT_ID = "d93926e2264775ad"
MQTT_OUT_ID = "4fd2979510810d5f"
TUYA_ID = "8ed219bf73293e78"
CHART_FN_ID = "d803759f55603ec6"
FN_SQLITE_ID = "cf_phw_fn_sqlite01"
HTTP_SENSOR_ID = "cf_phw_http_sensor01"

PICK_IDS = [
    "d5483828b614bd88",
    "874f552956291ad6",
    "4fa53d4c97a59637",
    "b22f8d4f771bb409",
    "f951ab2f0f813b4d",
    "9651686f7f601ac8",
]

GAUGE_RENAME = {
    "480e017a1bfbfe7b": "Cronus pH",
    "2141fe178c3e2c88": "Cronus EC",
    "a0a33715ba8ca5eb": "Cronus TDS",
    "f61aebaa74026feb": "Cronus SALT",
    "9d76b919dae993f9": "Cronus S.G",
    "1800ba1474d7135c": "Cronus Temp",
    "d7b0b47e7833847a": "Cronus PHW3988 24h",
}


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


def patch_fn_map_wires(n: dict) -> None:
    n["wires"] = [
        [
            *PICK_IDS,
            CHART_FN_ID,
            FN_MQTT_ID,
            FN_SQLITE_ID,
        ]
    ]


def ensure_sqlite_nodes(by_id: dict[str, dict]) -> None:
    by_id[FN_SQLITE_ID] = {
        "id": FN_SQLITE_ID,
        "type": "function",
        "z": PHW_TAB,
        "name": "PHW→SQLite sensor",
        "func": (
            "const dis = (env.get('CRONUSFARM_SQLITE_DISABLE') || '').toString().trim();\n"
            "if (dis === '1' || dis.toLowerCase() === 'true') return null;\n"
            "const p = msg.payload || {};\n"
            "const minMs = parseInt((env.get('CRONUSFARM_PHW_SQLITE_MIN_MS') || '30000').toString(), 10) || 30000;\n"
            "const now = Date.now();\n"
            "const last = flow.get('lastPhwSensorMs') || 0;\n"
            "if (now - last < minMs) return null;\n"
            "flow.set('lastPhwSensorMs', now);\n"
            "const base = (env.get('CRONUSFARM_SQLITE_BRIDGE_URL') || 'http://127.0.0.1:18766').toString().replace(/\\/$/, '');\n"
            "msg.method = 'POST';\n"
            "msg.url = base + '/ingest/sensor';\n"
            "msg.headers = { 'Content-Type': 'application/json; charset=utf-8' };\n"
            "msg.payload = JSON.stringify({\n"
            "  device_id: 'cronusfarm-01',\n"
            "  zone: 'phw3988',\n"
            "  ph: p.ph,\n"
            "  ec: p.ec,\n"
            "  temp_c: p.temp,\n"
            "  source: 'phw3988',\n"
            "  raw_json: JSON.stringify(p),\n"
            "  ts_ms: now\n"
            "});\n"
            "return msg;"
        ),
        "outputs": 1,
        "timeout": 0,
        "noerr": 0,
        "initialize": "",
        "finalize": "",
        "libs": [],
        "x": 590,
        "y": 400,
        "wires": [[HTTP_SENSOR_ID]],
    }
    by_id[HTTP_SENSOR_ID] = {
        "id": HTTP_SENSOR_ID,
        "type": "http request",
        "z": PHW_TAB,
        "name": "SQLite HTTP sensor",
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
        "x": 820,
        "y": 400,
        "wires": [[]],
    }


def patch_node(n: dict) -> dict | None:
    nid = n.get("id")
    if nid in DROP_IDS:
        return None

    t = n.get("type")
    if t == "mqtt-broker" and "hivemq" in str(n.get("broker", "")).lower():
        return None

    node = dict(n)
    if "wires" in node:
        node["wires"] = strip_wires(node["wires"], DROP_IDS)

    if nid == TUYA_ID:
        node["deviceIp"] = "14.32.231.191"
        node["wires"] = [[FN_MAP_ID], []]

    if nid == FN_MAP_ID:
        node["func"] = re.sub(
            r"const DEVICE = 'phw3988';",
            "const DEVICE = 'cronus';",
            node.get("func", ""),
        )
        patch_fn_map_wires(node)

    if nid == FN_MQTT_ID:
        node["name"] = "to Cronus/water JSON"
        node["func"] = (
            "const p = msg.payload || {};\n"
            "let obj = p;\n"
            "if (typeof obj === 'string') {\n"
            "  try { obj = JSON.parse(obj); } catch (e) { return null; }\n"
            "}\n"
            "if (!obj || typeof obj !== 'object') return null;\n"
            "const out = { ph: obj.ph, ec: obj.ec, temp: obj.temp };\n"
            "if (out.ph === undefined && out.ec === undefined && out.temp === undefined) return null;\n"
            "msg.topic = 'cronus/water';\n"
            "msg.payload = JSON.stringify(out);\n"
            "return msg;\n"
        )

    if nid == MQTT_OUT_ID:
        node["name"] = "To Arduino (Cronus/water)"
        node["broker"] = MOSQUITTO
        node["topic"] = "cronus/water"

    if nid == CHART_FN_ID:
        f = node.get("func", "")
        if "phw3988" in f or "phc493" in f:
            node["func"] = f.replace("phw3988", "cronus").replace("phc493", "cronus")

    if nid in GAUGE_RENAME:
        node["name"] = GAUGE_RENAME[nid]

    if "sf_3team" in json.dumps(node, ensure_ascii=False):
        s = json.dumps(node, ensure_ascii=False)
        s = s.replace("sf_3team", "cronus").replace("SF_3TEAM", "CRONUS")
        node = json.loads(s)

    return node


def prune_hive_from_json(json_path: Path) -> int:
    """HIVEMQ 브로커·미사용 PHW 노드 제거, mqtt out 브로커는 Mosquitto로."""
    if not json_path.is_file():
        return 0
    raw: list = json.loads(json_path.read_text(encoding="utf-8-sig"))
    drop: set[str] = set()
    for n in raw:
        if not isinstance(n, dict):
            continue
        if n.get("type") == "mqtt-broker" and "hivemq" in str(n.get("broker", "")).lower():
            if isinstance(n.get("id"), str):
                drop.add(n["id"])
    drop |= DROP_IDS
    if not drop:
        return 0

    def strip_w(wires: object) -> object:
        if not isinstance(wires, list):
            return w
        out = []
        for branch in wires:
            if not isinstance(branch, list):
                out.append(branch)
                continue
            out.append([x for x in branch if x not in drop])
        return out

    out: list = []
    removed = 0
    for n in raw:
        if not isinstance(n, dict):
            out.append(n)
            continue
        if n.get("id") in drop:
            removed += 1
            continue
        node = dict(n)
        if "broker" in node and node.get("broker") in drop:
            node["broker"] = MOSQUITTO
        if "wires" in node:
            node["wires"] = strip_w(node["wires"])
        out.append(node)
    json_path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    if removed:
        print(f"OK {json_path.name}: HIVEMQ 등 {removed}개 제거")
    return removed


def prune_hive_all_splits() -> None:
    for name in (
        "flows_cronusfarm_mqtt.json",
        "flows_cronusfarm_devflow_flow.json",
    ):
        prune_hive_from_json(ROOT / "nodered" / name)


def main() -> int:
    if not PI_PATH.is_file():
        print(f"없음: {PI_PATH}", file=sys.stderr)
        return 1

    raw: list = json.loads(PI_PATH.read_text(encoding="utf-8-sig"))
    by_id: dict[str, dict] = {}
    for n in raw:
        if not isinstance(n, dict):
            continue
        patched = patch_node(n)
        if patched is None:
            continue
        nid = patched.get("id")
        if isinstance(nid, str) and nid:
            by_id[nid] = patched

    ensure_sqlite_nodes(by_id)
    if FN_MAP_ID in by_id:
        patch_fn_map_wires(by_id[FN_MAP_ID])

    # PHW 탭 info
    tab = by_id.get(PHW_TAB)
    if isinstance(tab, dict) and tab.get("type") == "tab":
        tab["info"] = (
            "PHW3988 (Tuya) → 14.32.231.191 → 모니터 게이지/차트 + SQLite sensor_reading + Mosquitto cronus/water"
        )

    out = list(by_id.values())
    PI_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=4), encoding="utf-8")
    print(f"OK patched {PI_PATH.name} nodes={len(out)} (dropped HIVEMQ/debug/split)")

    prune_hive_all_splits()

    rebuild = ROOT / "scripts" / "rebuild_dashboard_split_from_pi.py"
    merge = ROOT / "scripts" / "merge_nodered_deploy.py"
    r = subprocess.run([sys.executable, str(rebuild)], cwd=str(ROOT))
    if r.returncode != 0:
        return r.returncode
    prune_hive_all_splits()
    r = subprocess.run([sys.executable, str(merge), "--use-split"], cwd=str(ROOT))
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
