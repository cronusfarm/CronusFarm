"""
Pi/로컬보내기(flows_pi_editor_latest.json)에서 CronusFarm 대시보드 분할 JSON을 재생성한다.

- Dashboard 1: tab_cronus_dash, ui_* (z 없음)
- Dashboard 2 제거: type이 ui- 로 시작하거나 ui-template
- NRDB2 전용 Function f1e2d3c4b5a6800f 제거
- PHW3988 플로우 탭(02ccfe788704ab49) 노드는 z를 tab_cronus_dash 로 옮겨 /ui 모니터(온실 Data)에 표시
- PHW → water MQTT out 은 로컬 Mosquitto 브로커 id(d6b7f6c1b2b3c4d5)로 통일
- devflow 에서 PHW 탭 하위 노드 제거(중복 방지, 탭 행만 유지)
- mqtt: 스케줄 브리지 응답을 모니터 ui_text 로 복제

사용: python scripts/rebuild_dashboard_split_from_pi.py
그 후: python scripts/merge_nodered_deploy.py --use-split
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PI_PATH = ROOT / "nodered" / "flows_pi_editor_latest.json"
OUT_PATH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
DEVFLOW_PATH = ROOT / "nodered" / "flows_cronusfarm_devflow_flow.json"

ALLOW_TAB = frozenset({"tab_cronus_dash"})
PHW_FLOW_TAB = "02ccfe788704ab49"
EXPLICIT_DROP_IDS = frozenset(
    {
        "f1e2d3c4b5a6800f",
        "d7013a5209d5fe9b",  # HIVEMQ
        "2c66449a4d7d4656",  # RAW DP debug
        "554c1b474239d145",  # aquarium split
    }
)


def is_dashboard2(n: dict) -> bool:
    t = n.get("type") or ""
    if t.startswith("ui-"):
        return True
    if t == "ui-template":
        return True
    return False


def should_keep_node(n: object) -> bool:
    if not isinstance(n, dict):
        return False
    z = n.get("z")
    t = n.get("type")
    tid = n.get("id")
    if tid in EXPLICIT_DROP_IDS:
        return False
    if t == "tab" and tid in ALLOW_TAB:
        return True
    if z in ALLOW_TAB:
        return True
    if isinstance(t, str) and t.startswith("ui_") and z is None:
        return True
    return False


def patch_tab_info(n: dict) -> None:
    if n.get("type") != "tab" or n.get("id") != "tab_cronus_dash":
        return
    info = (n.get("info") or "").strip()
    if not info:
        return
    lines = [
        ln
        for ln in info.splitlines()
        if "nrdb2" not in ln.lower() and "dashboard 2" not in ln.lower()
    ]
    n["info"] = "\n".join(lines).strip()


def patch_gh_group_name(n: dict) -> None:
    if n.get("id") == "ui_grp_gh_data" and n.get("type") == "ui_group":
        n["name"] = "온실 Data (PHW3988)"


def patch_shell_usage_no_nrdb2(n: dict) -> None:
    if n.get("id") != "ui_tpl_shell_panel_usage" or n.get("type") != "ui_template":
        return
    fmt = n.get("format")
    if not isinstance(fmt, str):
        return
    n["format"] = fmt.replace("Dashboard 2: <code>/nrdb2</code>. ", "")


def strip_wire_targets(wires: object, drop: set[str]) -> object:
    if not isinstance(wires, list):
        return wires
    out: list = []
    for branch in wires:
        if not isinstance(branch, list):
            out.append(branch)
            continue
        out.append([x for x in branch if isinstance(x, str) and x not in drop])
    return out


def prune_phw_nodes_from_devflow() -> int:
    if not DEVFLOW_PATH.is_file():
        return 0
    raw = json.loads(DEVFLOW_PATH.read_text(encoding="utf-8-sig"))
    out: list = []
    removed = 0
    for n in raw:
        if not isinstance(n, dict):
            out.append(n)
            continue
        if n.get("z") == PHW_FLOW_TAB and n.get("type") != "tab":
            removed += 1
            continue
        out.append(n)
    DEVFLOW_PATH.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    if removed:
        print(f"OK devflow: PHW 탭 노드 {removed}개 제거(탭 행만 유지)")
    return removed


def append_schedule_monitor_nodes(by_id: dict[str, dict]) -> None:
    if "cf_lki_sch_mon01" in by_id:
        return
    extra = [
        {
            "id": "cf_lki_sch_mon01",
            "type": "link in",
            "z": "tab_cronus_dash",
            "name": "스케줄 API→모니터",
            "links": ["cf_lko_sch_mon01"],
            "x": 40,
            "y": 1240,
            "wires": [["ui_txt_mon_sched01"]],
        },
        {
            "id": "ui_txt_mon_sched01",
            "type": "ui_text",
            "z": "tab_cronus_dash",
            "group": "ui_grp_farm",
            "order": 2,
            "width": 0,
            "height": 0,
            "name": "스케줄 저장/조회(브리지 응답)",
            "label": "스케줄 API",
            "format": "{{msg.payload}}",
            "layout": "row-spread",
            "x": 200,
            "y": 1240,
            "wires": [],
        },
    ]
    for n in extra:
        by_id[n["id"]] = n


def patch_mqtt_schedule_fanout() -> None:
    mqtt_path = ROOT / "nodered" / "flows_cronusfarm_mqtt.json"
    data: list = json.loads(mqtt_path.read_text(encoding="utf-8-sig"))
    by_id = {n["id"]: n for n in data if isinstance(n, dict) and n.get("id")}
    if "cf_fn_sch_notify01" in by_id:
        return
    hr = by_id.get("cf_hreq_sch")
    if not hr:
        print("WARN: cf_hreq_sch 없음 — mqtt 패치 생략", file=sys.stderr)
        return
    hr["wires"] = [["cf_fn_sch_notify01"]]
    fn_sch = {
        "id": "cf_fn_sch_notify01",
        "type": "function",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "스케줄 응답→HTTP+모니터",
        "func": (
            "// SQLite 스케줄 GET/PUT 브리지 응답: HTTP 유지 + 모니터용 텍스트\n"
            "let line = '';\n"
            "try {\n"
            "  const raw = msg.payload;\n"
            "  const j = typeof raw === 'string' ? JSON.parse(raw) : raw;\n"
            "  if (j && typeof j === 'object') {\n"
            "    line = '[스케줄] ' + new Date().toISOString() + '\\n' + JSON.stringify(j, null, 2);\n"
            "    if (line.length > 1800) line = line.slice(0, 1800) + '\\n…(생략)';\n"
            "  } else {\n"
            "    line = String(raw || '').slice(0, 800);\n"
            "  }\n"
            "} catch (e) {\n"
            "  line = String(msg.payload || '').slice(0, 600);\n"
            "}\n"
            "return [msg, { payload: line }];\n"
        ),
        "outputs": 2,
        "timeout": 0,
        "noerr": 0,
        "initialize": "",
        "finalize": "",
        "libs": [],
        "x": 820,
        "y": 540,
        "wires": [["cf_hres_sch"], ["cf_lko_sch_mon01"]],
    }
    lko = {
        "id": "cf_lko_sch_mon01",
        "type": "link out",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "→모니터 스케줄 텍스트",
        "mode": "link",
        "links": ["cf_lki_sch_mon01"],
        "x": 1020,
        "y": 560,
        "wires": [],
    }
    data.extend([fn_sch, lko])
    mqtt_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print("OK mqtt: 스케줄 응답 분기(cf_fn_sch_notify01 + link out)")


def main() -> int:
    if not PI_PATH.is_file():
        print(f"없음: {PI_PATH}", file=sys.stderr)
        return 1
    data: list = json.loads(PI_PATH.read_text(encoding="utf-8-sig"))
    drop_ids = {
        n["id"]
        for n in data
        if isinstance(n, dict) and isinstance(n.get("id"), str) and is_dashboard2(n)
    }
    drop_ids |= EXPLICIT_DROP_IDS
    for n in data:
        if (
            isinstance(n, dict)
            and n.get("type") == "mqtt-broker"
            and "hivemq" in str(n.get("broker", "")).lower()
            and isinstance(n.get("id"), str)
        ):
            drop_ids.add(n["id"])

    by_id: dict[str, dict] = {}
    for n in data:
        if not isinstance(n, dict):
            continue
        if not should_keep_node(n):
            continue
        nid = n.get("id")
        if not isinstance(nid, str) or nid in drop_ids:
            continue
        node = dict(n)
        patch_tab_info(node)
        patch_shell_usage_no_nrdb2(node)
        patch_gh_group_name(node)
        if "wires" in node:
            node["wires"] = strip_wire_targets(node["wires"], drop_ids)
        by_id[nid] = node

    dash_tab = "tab_cronus_dash"
    for n in data:
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        if not isinstance(nid, str) or nid in drop_ids:
            continue
        if n.get("z") != PHW_FLOW_TAB or n.get("type") == "tab":
            continue
        node = dict(n)
        node["z"] = dash_tab
        if nid == "4fd2979510810d5f" and node.get("type") == "mqtt out":
            node["broker"] = "d6b7f6c1b2b3c4d5"
            node["topic"] = "cronus/water"
            node["name"] = "To Arduino (Cronus/water)"
        if nid == "d93926e2264775ad" and node.get("type") == "function":
            node["name"] = "to Cronus/water JSON"
        if nid == "8ed219bf73293e78" and node.get("type") == "tuya-smart-device":
            node["deviceIp"] = "14.32.231.191"
        if "wires" in node:
            node["wires"] = strip_wire_targets(node["wires"], drop_ids)
        by_id[nid] = node

    g = by_id.get("ui_grp_gh_data")
    if isinstance(g, dict):
        patch_gh_group_name(g)

    append_schedule_monitor_nodes(by_id)

    kept = list(by_id.values())
    OUT_PATH.write_text(json.dumps(kept, ensure_ascii=False), encoding="utf-8")
    print(f"OK {OUT_PATH.name} nodes={len(kept)} (drop D2+orphan {len(drop_ids)})")

    prune_phw_nodes_from_devflow()
    patch_mqtt_schedule_fanout()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
