# -*- coding: utf-8 -*-
"""MQTT/R4 연결 끊김 시 Telegram 알림 (상태 전이·재알림 간격).

- fn_calc_online 출력에 cf_fn_conn_offline_tg 연결 → cf_fn_tg_prep
- retain status 'offline' 수신 시 cf_fn_mqtt_retain_offline_tg (병렬)
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAB_MQTT = "b1c5a1f1d7a2a3a1"
TAB_DASH = "tab_cronus_dash"

FN_CONN = r"""// R4 MQTT 연결 끊김 → Telegram (connLineOk 전이)
const ok = msg.connLineOk === true;
const prev = flow.get('cfConnLineOkPrev');
const minMs = parseInt((env.get('CRONUSFARM_TG_OFFLINE_ALERT_MIN_MS') || '300000').toString(), 10) || 300000;
const now = Date.now();
const lastAlert = flow.get('cfTgOfflineAlertMs') || 0;
flow.set('cfConnLineOkPrev', ok);
if (ok) { return null; }
const transitioned = (prev === true || prev === undefined);
if (!transitioned && (now - lastAlert) < minMs) { return null; }
flow.set('cfTgOfflineAlertMs', now);
const retain = (msg.statusRetain || '').toString().trim() || '—';
const teleAge = (msg.teleAge != null) ? (String(msg.teleAge) + '초') : '—';
const text = [
  '⚠️ CronusFarm MQTT 연결 끊김',
  '표시: ' + (retain === 'offline' ? 'status offline' : 'tele 미수신/타임아웃'),
  'retain: ' + retain,
  'tele 미수신: ' + teleAge,
  '시각: ' + new Date().toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })
].join('\n');
return { req: { query: { text } } };"""

FN_RETAIN = r"""// MQTT status retain offline → Telegram
const dis = (env.get('CRONUSFARM_TG_OFFLINE_ALERT_DISABLE') || '').toString().trim();
if (dis === '1') { return null; }
let pl = msg.payload;
let st = '';
if (typeof pl === 'string') {
  st = pl.trim();
  try {
    const o = JSON.parse(pl);
    if (o && o.state) { st = String(o.state).trim(); }
  } catch (e) { /* plain */ }
} else if (pl && typeof pl === 'object' && pl.state) {
  st = String(pl.state).trim();
}
st = st.toLowerCase().replace(/^['\"]+|['\"]+$/g, '');
if (st !== 'offline') { return null; }
const prev = flow.get('cfMqttRetainStatus');
flow.set('cfMqttRetainStatus', st);
if (prev === 'offline') { return null; }
const minMs = parseInt((env.get('CRONUSFARM_TG_OFFLINE_ALERT_MIN_MS') || '300000').toString(), 10) || 300000;
const now = Date.now();
const lastAlert = flow.get('cfTgOfflineAlertMs') || 0;
if ((now - lastAlert) < minMs) { return null; }
flow.set('cfTgOfflineAlertMs', now);
const text = [
  '⚠️ CronusFarm MQTT status: offline',
  '토픽: ' + ((msg.topic || '').toString()),
  '시각: ' + new Date().toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })
].join('\n');
return { req: { query: { text } } };"""


def _upsert(flows: list, node: dict) -> None:
    nid = node["id"]
    for i, n in enumerate(flows):
        if isinstance(n, dict) and n.get("id") == nid:
            flows[i] = {**n, **node}
            return
    flows.append(node)


def _wire_append(node: dict, target: str) -> None:
    w = node.get("wires") or [[]]
    if not w:
        w = [[]]
    if target not in w[0]:
        w[0].append(target)
    node["wires"] = w


def patch_mqtt(path: Path) -> bool:
    flows = json.loads(path.read_text(encoding="utf-8-sig"))
    ids = {n.get("id") for n in flows if isinstance(n, dict)}

    _upsert(
        flows,
        {
            "id": "cf_fn_conn_offline_tg",
            "type": "function",
            "z": TAB_MQTT,
            "name": "MQTT 끊김 Telegram",
            "func": FN_CONN,
            "outputs": 1,
            "timeout": 0,
            "noerr": 0,
            "initialize": "",
            "finalize": "",
            "libs": [],
            "x": 1180,
            "y": 520,
            "wires": [["cf_fn_tg_prep"]],
        },
    )
    _upsert(
        flows,
        {
            "id": "cf_fn_mqtt_retain_offline_tg",
            "type": "function",
            "z": TAB_MQTT,
            "name": "status offline Telegram",
            "func": FN_RETAIN,
            "outputs": 1,
            "timeout": 0,
            "noerr": 0,
            "initialize": "",
            "finalize": "",
            "libs": [],
            "x": 520,
            "y": 200,
            "wires": [["cf_fn_tg_prep"]],
        },
    )

    status_in = next((n for n in flows if n.get("id") == "sq_mqtt_in_status"), None)
    if status_in:
        _wire_append(status_in, "cf_fn_mqtt_retain_offline_tg")

    path.write_text(json.dumps(flows, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    print("OK mqtt:", path)
    return True


def patch_dashboard(path: Path) -> bool:
    flows = json.loads(path.read_text(encoding="utf-8-sig"))
    calc = next((n for n in flows if n.get("id") == "fn_calc_online"), None)
    if not calc:
        print("SKIP no fn_calc_online in", path)
        return False
    _wire_append(calc, "cf_fn_conn_offline_tg")
    path.write_text(json.dumps(flows, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    print("OK dashboard:", path)
    return True


def main() -> None:
    mqtt = ROOT / "nodered" / "flows_cronusfarm_mqtt.json"
    dash = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
    patch_mqtt(mqtt)
    patch_dashboard(dash)
    mono = ROOT / "nodered" / "CronusFarm_NodeRED_flow.json"
    if mono.is_file():
        patch_mqtt(mono)
        patch_dashboard(mono)


if __name__ == "__main__":
    main()
