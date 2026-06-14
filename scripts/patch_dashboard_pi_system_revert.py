# -*- coding: utf-8 -*-
"""System (Pi : ida) — patch_dashboard_pi_system_layout 변경 원상 복구."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FLOW_FILES = [
    ROOT / "nodered" / "flows_cronusfarm_dashboard.json",
    ROOT / "nodered" / "flows_cronusfarm_mqtt.json",
    ROOT / "nodered" / "merged-deploy.json",
    ROOT / "nodered" / "CronusFarm_NodeRED_flow.json",
]

REMOVE_IDS = frozenset(
    {
        "ui_tpl_pi_system",
        "fn_pi_system_merge",
        "exec_wan_ip",
        "fn_trim_wan_ip",
    }
)

TRIM_RESTORE = {
    "fn_trim_uptime": "msg.payload = (msg.payload||'').toString().trim() || '—';\nreturn msg;",
    "fn_trim_ssid": "msg.payload = (msg.payload||'').toString().trim() || '(미연결)';\nreturn msg;",
    "fn_trim_ip": "const s=(msg.payload||'').toString().trim();\nmsg.payload = (s.split(/\\s+/)[0]||'—');\nreturn msg;",
    "fn_trim_ts_ip": "msg.payload = (msg.payload||'').toString().trim() || '—';\nreturn msg;",
}

TRIM_WIRES = {
    "fn_trim_uptime": ["ui_txt_uptime"],
    "fn_trim_ssid": ["ui_txt_ssid"],
    "fn_trim_ip": ["ui_txt_ip"],
    "fn_trim_ts_ip": ["ui_txt_ts_ip"],
}

SHOW_TEXT = {
    "ui_txt_uptime": (6, 1, 1, "Booting Time"),
    "ui_txt_ssid": (6, 1, 2, "Pi WiFi SSID"),
    "ui_txt_ip": (6, 1, 3, "Pi IP"),
    "ui_txt_ts_ip": (6, 1, 4, "Pi Tailscale IP"),
    "ui_txt_pi_host": (12, 1, 5, "Pi 도메인"),
}

PI_ORDER = {
    "ui_txt_uptime": 1,
    "ui_txt_ssid": 2,
    "ui_txt_ip": 3,
    "ui_txt_ts_ip": 4,
    "ui_txt_pi_host": 5,
    "ui_txt_pi_tick": 6,
    "ui_tpl_pi_nodered": 7,
    "ui_tpl_pi_mosq": 8,
}


def _strip_wires(wires: list, drop: set[str]) -> list:
    out: list = []
    for port in wires:
        if not isinstance(port, list):
            out.append(port)
            continue
        out.append([x for x in port if x not in drop])
    return out


def patch_file(path: Path) -> list[str]:
    if not path.is_file():
        return []
    flows = json.loads(path.read_text(encoding="utf-8-sig"))
    changed: list[str] = []
    before = len(flows)
    flows = [n for n in flows if not (isinstance(n, dict) and n.get("id") in REMOVE_IDS)]
    if len(flows) < before:
        changed.append("remove_pi_template_nodes")

    for n in flows:
        if not isinstance(n, dict):
            continue
        nid = n.get("id")

        if nid in TRIM_RESTORE and n.get("func") != TRIM_RESTORE[nid]:
            n["func"] = TRIM_RESTORE[nid]
            changed.append(nid)
        if nid in TRIM_WIRES:
            want = TRIM_WIRES[nid]
            if n.get("wires") != [want]:
                n["wires"] = [want]
                changed.append(f"{nid}_wires")

        if nid in SHOW_TEXT:
            w, h, order, label = SHOW_TEXT[nid]
            if n.get("width") != w:
                n["width"] = w
                changed.append(f"show:{nid}")
            if n.get("height") != h:
                n["height"] = h
            if n.get("order") != order:
                n["order"] = order
            if n.get("label") != label:
                n["label"] = label

        if n.get("group") == "ui_grp_pi" and nid in PI_ORDER and n.get("order") != PI_ORDER[nid]:
            n["order"] = PI_ORDER[nid]
            changed.append(f"order:{nid}")

        if nid == "inj_sys_10s" and isinstance(n.get("wires"), list) and n["wires"]:
            w0 = _strip_wires(n["wires"], REMOVE_IDS)[0]
            if w0 != n["wires"][0]:
                n["wires"][0] = w0
                changed.append("inj_sys_10s")

        if nid == "fn_pi_status_route" and isinstance(n.get("wires"), list):
            nw = _strip_wires(n["wires"], REMOVE_IDS)
            if nw != n["wires"]:
                n["wires"] = nw
                changed.append("fn_pi_status_route")

    if changed:
        path.write_text(
            json.dumps(flows, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    return [f"{path.name}:{c}" for c in changed]


def main() -> int:
    all_c: list[str] = []
    for fp in FLOW_FILES:
        all_c.extend(patch_file(fp))
    if not all_c:
        print("WARN patch_dashboard_pi_system_revert: no changes")
        return 1
    print("OK patch_dashboard_pi_system_revert:", ", ".join(sorted(set(all_c))[:20]), "...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
