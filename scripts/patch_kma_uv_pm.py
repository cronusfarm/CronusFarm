# -*- coding: utf-8 -*-
"""KMA 자외선·미세먼지: NCST 스냅샷에 UV/PM 병합 + 30분마다 pi-kma-refresh 실행."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MQTT = ROOT / "nodered" / "flows_cronusfarm_mqtt.json"
FLOW_FILES = [
    MQTT,
    ROOT / "nodered" / "merged-deploy.json",
    ROOT / "nodered" / "CronusFarm_NodeRED_flow.json",
]

MERGE_SNAP_JS = r"""
// UV·PM10: 초단기실황 API에 없음 — 캐시·pi-kma-refresh 값 유지
const prev = global.get('kmaSnapshot') || flow.get('kmaSnapshot') || {};
for (const k of ['kma_uv_index', 'kma_pm10', 'kma_pm10_grade']) {
  if ((snap[k] === null || snap[k] === undefined || snap[k] === '') && prev[k] != null && prev[k] !== '') {
    snap[k] = prev[k];
  }
}
const merged = Object.assign({}, prev, snap);
global.set('kmaSnapshot', merged);
flow.set('kmaSnapshot', merged);
"""

INJ_NODE = {
    "id": "inj_kma_uv_pm",
    "type": "inject",
    "z": "b1c5a1f1d7a2a3a1",
    "name": "KMA UV/PM 30분",
    "props": [{"p": "payload"}],
    "repeat": "1800",
    "crontab": "",
    "once": True,
    "onceDelay": "45",
    "topic": "",
    "payload": "",
    "payloadType": "date",
    "x": 120,
    "y": 520,
    "wires": [["exec_kma_uv_pm"]],
}

EXEC_NODE = {
    "id": "exec_kma_uv_pm",
    "type": "exec",
    "z": "b1c5a1f1d7a2a3a1",
    "command": "python3",
    "addpay": "append",
    "append": "",
    "useSpawn": "false",
    "timer": "",
    "winHide": False,
    "oldrc": False,
    "name": "pi-kma-refresh (UV·PM)",
    "x": 360,
    "y": 520,
    "wires": [[], []],
}


def _patch_fn_kma_to_influx(func: str) -> str:
    if "kma_uv_index" in func and "pi-kma-refresh" in func:
        return func
    anchor = "const snap = {"
    if anchor not in func:
        return func
    end = func.find("};", func.find(anchor))
    if end < 0:
        return func
    insert_at = end + 2
    return func[:insert_at] + MERGE_SNAP_JS + func[insert_at:]


def _ensure_uv_pm_nodes(flows: list) -> bool:
    by_id = {n.get("id"): n for n in flows if isinstance(n, dict) and n.get("id")}
    changed = False
    if "inj_kma_uv_pm" not in by_id:
        flows.append(dict(INJ_NODE))
        changed = True
    if "exec_kma_uv_pm" not in by_id:
        ex = dict(EXEC_NODE)
        ex["append"] = "/home/dooly/CronusFarm/scripts/pi-kma-refresh-now.py"
        flows.append(ex)
        changed = True
    elif not (by_id["exec_kma_uv_pm"].get("append") or "").endswith("pi-kma-refresh-now.py"):
        by_id["exec_kma_uv_pm"]["append"] = str(ROOT / "scripts" / "pi-kma-refresh-now.py")
        changed = True
    return changed


def patch_file(path: Path) -> list[str]:
    if not path.is_file():
        return []
    flows = json.loads(path.read_text(encoding="utf-8-sig"))
    changed: list[str] = []
    for n in flows:
        if n.get("id") == "fn_kma_to_influx" and n.get("type") == "function":
            new_func = _patch_fn_kma_to_influx(n.get("func") or "")
            if new_func != n.get("func"):
                n["func"] = new_func
                changed.append("fn_kma_to_influx")
    if path == MQTT and _ensure_uv_pm_nodes(flows):
        changed.append("inj_kma_uv_pm+exec")
    if changed:
        path.write_text(
            json.dumps(flows, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    return changed


def main() -> int:
    for fp in FLOW_FILES:
        ch = patch_file(fp)
        if ch:
            print(f"OK {fp.name}: {', '.join(ch)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
