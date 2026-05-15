"""
PHW3988 → 모니터 게이지·DB·Cronus MQTT 통합 패치.

- sf_3team → cronus
- HIVEMQ·중복 Mosquitto(mqtt_broker_pi) 제거
- ui_grp_gh_data 를 dashboard 에 추가, PHW 노드를 dashboard 로 이동
- SQLite sensor 적재 + inject 로 DB 최신값 → 게이지
- Bed 타임라인(ui_tpl_hist*)·설정 탭 노드는 dashboard 에서 변경하지 않음

사용:
  python scripts/patch_phw3988_monitor_integrate.py
  python scripts/merge_nodered_deploy.py --use-split
"""
from __future__ import annotations

import json
import re
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
DEV = ROOT / "nodered" / "flows_cronusfarm_devflow_flow.json"
MQTT = ROOT / "nodered" / "flows_cronusfarm_mqtt.json"

MOSQUITTO = "d6b7f6c1b2b3c4d5"
DROP_BROKER = "mqtt_broker_pi"
HIVE_ID = "d7013a5209d5fe9b"
DASH_Z = "tab_cronus_dash"
MON_TAB = "ui_tab_monitor"
GH_GROUP = "ui_grp_gh_data"
PUBLIC_IP = "14.32.231.191"

PICK_IDS = [
    "d5483828b614bd88",
    "874f552956291ad6",
    "4fa53d4c97a59637",
    "b22f8d4f771bb409",
    "f951ab2f0f813b4d",
    "9651686f7f601ac8",
]
CHART_FN = "d803759f55603ec6"
CHART_UI = "d7b0b47e7833847a"
FN_MAP = "201f991e49bff34f"
FN_MQTT_JSON = "d93926e2264775ad"
MQTT_OUT = "4fd2979510810d5f"
TUYA = "8ed219bf73293e78"
FN_SQLITE = "cf_phw_fn_sqlite01"
HTTP_SQLITE = "cf_phw_http_sensor01"
INJECT_GAUGE = "cf_phw_inj_gauge01"
FN_READ_API = "cf_phw_fn_read_api01"
HTTP_READ = "cf_phw_http_read01"
FN_TO_GAUGES = "cf_phw_fn_to_gauges01"

PHW_MOVE_IDS = frozenset(
    {
        TUYA,
        FN_MAP,
        FN_MQTT_JSON,
        MQTT_OUT,
        FN_SQLITE,
        HTTP_SQLITE,
        INJECT_GAUGE,
        FN_READ_API,
        HTTP_READ,
        FN_TO_GAUGES,
        *PICK_IDS,
        "480e017a1bfbfe7b",
        "2141fe178c3e2c88",
        "a0a33715ba8ca5eb",
        "f61aebaa74026feb",
        "9d76b919dae993f9",
        "1800ba1474d7135c",
        CHART_FN,
        CHART_UI,
    }
)

DEV_KEEP_PREFIX = (
    "ui_tpl_devflow",
    "cf_tpl_dev",
    "cf_grp_dev",
    "cmt_devflow",
    "tab_cronus_devflow",
    "02ccfe788704ab49",
    "fd_",
)


def load(path: Path) -> list:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(path: Path, data: list) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


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


def rename_sf_to_cronus(node: dict) -> None:
    s = json.dumps(node, ensure_ascii=False)
    if "sf_3team" not in s.lower():
        return
    s = s.replace("sf_3team", "cronus").replace("SF_3TEAM", "CRONUS")
    s = s.replace("To Arduino (sf_3team/water)", "To Arduino (Cronus/water)")
    s = s.replace("to sf_3team/water JSON", "to Cronus/water JSON")
    updated = json.loads(s)
    node.clear()
    node.update(updated)


def patch_mqtt_brokers(data: list) -> None:
    drop: set[str] = {HIVE_ID, DROP_BROKER}
    out: list = []
    for n in data:
        if not isinstance(n, dict):
            out.append(n)
            continue
        nid = n.get("id")
        if nid in drop:
            continue
        if n.get("type") == "mqtt-broker" and "hivemq" in str(n.get("broker", "")).lower():
            continue
        node = dict(n)
        if node.get("broker") in drop:
            node["broker"] = MOSQUITTO
        if "wires" in node:
            node["wires"] = strip_wires(node["wires"], drop)
        out.append(node)
    data.clear()
    data.extend(out)


def ensure_gh_group(dash_by: dict[str, dict]) -> None:
    if GH_GROUP not in dash_by:
        dash_by[GH_GROUP] = {
            "id": GH_GROUP,
            "type": "ui_group",
            "name": "온실 Data (PHW3988)",
            "tab": MON_TAB,
            "order": 6,
            "disp": True,
            "width": "12",
            "collapse": False,
            "className": "",
        }
    else:
        g = dash_by[GH_GROUP]
        g["tab"] = MON_TAB
        g["name"] = "온실 Data (PHW3988)"


def new_sqlite_nodes() -> dict[str, dict]:
    fn_sql = {
        "id": FN_SQLITE,
        "type": "function",
        "z": DASH_Z,
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
            "  ph: p.ph, ec: p.ec, temp_c: p.temp,\n"
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
        "x": 520,
        "y": 1180,
        "wires": [[HTTP_SQLITE]],
    }
    http_sql = {
        "id": HTTP_SQLITE,
        "type": "http request",
        "z": DASH_Z,
        "name": "SQLite POST sensor",
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
        "x": 760,
        "y": 1180,
        "wires": [[]],
    }
    inj = {
        "id": INJECT_GAUGE,
        "type": "inject",
        "z": DASH_Z,
        "name": "게이지←DB 15s",
        "props": [{"p": "payload"}, {"p": "topic", "vt": "str"}],
        "repeat": "15",
        "crontab": "",
        "once": True,
        "onceDelay": "3",
        "topic": "",
        "payload": "",
        "payloadType": "date",
        "x": 120,
        "y": 1320,
        "wires": [[FN_READ_API]],
    }
    fn_read = {
        "id": FN_READ_API,
        "type": "function",
        "z": DASH_Z,
        "name": "GET sensor/latest",
        "func": (
            "const base = (env.get('CRONUSFARM_SQLITE_BRIDGE_URL') || 'http://127.0.0.1:18766').toString().replace(/\\/$/, '');\n"
            "msg.method = 'GET';\n"
            "msg.url = base + '/api/sensor/latest?device_id=cronusfarm-01&zone=phw3988';\n"
            "msg.headers = {};\n"
            "delete msg.payload;\n"
            "return msg;"
        ),
        "outputs": 1,
        "timeout": 0,
        "noerr": 0,
        "initialize": "",
        "finalize": "",
        "libs": [],
        "x": 320,
        "y": 1320,
        "wires": [[HTTP_READ]],
    }
    http_read = {
        "id": HTTP_READ,
        "type": "http request",
        "z": DASH_Z,
        "name": "SQLite GET latest",
        "method": "use",
        "ret": "obj",
        "paytoqs": "ignore",
        "url": "",
        "tls": "",
        "persist": False,
        "proxy": "",
        "insecureHTTPParser": False,
        "authType": "",
        "senderr": False,
        "headers": [],
        "x": 540,
        "y": 1320,
        "wires": [[FN_TO_GAUGES]],
    }
    fn_gauges = {
        "id": FN_TO_GAUGES,
        "type": "function",
        "z": DASH_Z,
        "name": "DB→게이지 payload",
        "func": (
            "let j = msg.payload;\n"
            "if (typeof j === 'string') { try { j = JSON.parse(j); } catch (e) { return null; } }\n"
            "if (!j || !j.ok) return null;\n"
            "let raw = j.raw_json;\n"
            "if (typeof raw === 'string') { try { raw = JSON.parse(raw); } catch (e) { raw = {}; } }\n"
            "const p = {\n"
            "  ph: j.ph != null ? j.ph : raw.ph,\n"
            "  ec: j.ec != null ? j.ec : raw.ec,\n"
            "  temp: j.temp_c != null ? j.temp_c : raw.temp,\n"
            "  tds: raw.tds, salt: raw.salt, sg: raw.sg\n"
            "};\n"
            "msg.payload = p;\n"
            "return msg;"
        ),
        "outputs": 1,
        "timeout": 0,
        "noerr": 0,
        "initialize": "",
        "finalize": "",
        "libs": [],
        "x": 760,
        "y": 1320,
        "wires": [PICK_IDS],
    }
    return {
        FN_SQLITE: fn_sql,
        HTTP_SQLITE: http_sql,
        INJECT_GAUGE: inj,
        FN_READ_API: fn_read,
        HTTP_READ: http_read,
        FN_TO_GAUGES: fn_gauges,
    }


def patch_phw_node(n: dict) -> dict:
    node = deepcopy(n)
    rename_sf_to_cronus(node)
    nid = node.get("id")
    if nid == TUYA:
        node["deviceIp"] = PUBLIC_IP
        node["z"] = DASH_Z
        node["wires"] = [[FN_MAP], []]
    elif nid == FN_MAP:
        node["z"] = DASH_Z
        # 게이지는 DB inject 경로만; 차트는 live 유지(타임라인·Bed 그래프 미변경)
        node["wires"] = [[FN_SQLITE, FN_MQTT_JSON, CHART_FN]]
    elif nid == FN_MQTT_JSON:
        node["z"] = DASH_Z
        f = node.get("func", "")
        if "cronus/water" not in f:
            node["func"] = re.sub(
                r"msg\.topic\s*=\s*['\"][^'\"]+['\"]",
                "msg.topic = 'cronus/water'",
                f,
            )
        node["wires"] = [[MQTT_OUT]]
    elif nid == MQTT_OUT:
        node["z"] = DASH_Z
        node["broker"] = MOSQUITTO
        node["topic"] = "cronus/water"
    elif node.get("type") == "ui_gauge":
        node["z"] = DASH_Z
        node["group"] = GH_GROUP
    elif node.get("type") == "ui_chart" and nid == CHART_UI:
        node["z"] = DASH_Z
        node["group"] = GH_GROUP
    elif nid == CHART_FN:
        node["z"] = DASH_Z
    elif node.get("type") == "change" and nid in PICK_IDS:
        node["z"] = DASH_Z
    return node


def integrate() -> None:
    dev = load(DEV)
    dash = load(DASH)
    mqtt = load(MQTT)

    patch_mqtt_brokers(mqtt)

    dash_by: dict[str, dict] = {}
    for n in dash:
        if isinstance(n, dict) and n.get("id"):
            dash_by[n["id"]] = n

    dev_by: dict[str, dict] = {}
    dev_out: list = []
    for n in dev:
        if not isinstance(n, dict):
            dev_out.append(n)
            continue
        nid = n.get("id")
        if not isinstance(nid, str):
            dev_out.append(n)
            continue
        if nid in PHW_MOVE_IDS:
            dev_by[nid] = n
            continue
        if any(nid.startswith(p) for p in DEV_KEEP_PREFIX) or n.get("type") in (
            "tab",
            "flexdash dashboard",
            "flexdash tab",
            "flexdash container",
            "ui_template",
            "ui_group",
            "comment",
        ):
            rename_sf_to_cronus(n)
            dev_out.append(n)

    ensure_gh_group(dash_by)
    for nid, n in dev_by.items():
        dash_by[nid] = patch_phw_node(n)

    for extra in new_sqlite_nodes().values():
        dash_by[extra["id"]] = extra

    if CHART_FN in dash_by:
        dash_by[CHART_FN]["wires"] = [[CHART_UI]]

    save(DASH, list(dash_by.values()))
    save(DEV, dev_out)
    save(MQTT, mqtt)
    print(
        f"OK dashboard={len(dash_by)} devflow={len(dev_out)} mqtt={len(mqtt)} "
        f"(PHW→모니터, sf_3team→cronus, HIVEMQ/중복 Mosquitto 제거)"
    )


def main() -> int:
    integrate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
