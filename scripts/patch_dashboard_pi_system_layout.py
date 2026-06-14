# -*- coding: utf-8 -*-
"""모니터 System (Pi) 카드: 2열 레이아웃·도메인/IP 행 정리."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_FMT = Path(__file__).resolve().parent / "_pi_system_fmt.txt"
PI_FMT = _FMT.read_text(encoding="utf-8").strip() if _FMT.is_file() else ""

FLOW_FILES = [
    ROOT / "nodered" / "flows_cronusfarm_dashboard.json",
    ROOT / "nodered" / "flows_cronusfarm_mqtt.json",
    ROOT / "nodered" / "merged-deploy.json",
    ROOT / "nodered" / "CronusFarm_NodeRED_flow.json",
]

FN_PI_SYS_MERGE = r"""const duck = (env.get('CRONUSFARM_PI_DUCKDNS') || 'cronusfarm.duckdns.org').toString().trim();
const tsHost = (env.get('CRONUSFARM_PI_HOST') || 'ida.mango-larch.ts.net').toString().trim();
msg.payload = {
  arduinoSsid: flow.get('arduino_wifi_ssid') || '—',
  arduinoIp: flow.get('arduino_wifi_ip') || '—',
  uptime: flow.get('pi_uptime') || '—',
  ssid: flow.get('pi_ssid') || '—',
  lanIp: flow.get('pi_lan_ip') || '—',
  wanIp: flow.get('pi_wan_ip') || '—',
  tsIp: flow.get('pi_ts_ip') || '—',
  duckDns: duck,
  tsHost: tsHost
};
return msg;"""

FN_ARDU_WIFI_STORE = r"""const s = (msg.payload || '').toString();
const parts = s.split('|').map(x => x.trim());
const w = parts.find(x => x.startsWith('W:'));
let ssid = '—';
let ip = '—';
if (w) {
  const rest = w.slice(2).trim();
  const k = rest.lastIndexOf(' ip=');
  if (k >= 0 && rest.startsWith('ssid=')) {
    ssid = rest.slice(5, k).trim() || '—';
    ip = rest.slice(k + 4).trim() || '—';
    if (ip === '0.0.0.0') ip = '—';
  }
}
flow.set('arduino_wifi_ssid', ssid);
flow.set('arduino_wifi_ip', ip);
return [[{ payload: ssid }], [{ payload: ip }]];"""

TRIM_UPTIME = r"""msg.payload = (msg.payload||'').toString().trim() || '—';
flow.set('pi_uptime', msg.payload);
return msg;"""

TRIM_SSID = r"""msg.payload = (msg.payload||'').toString().trim() || '(미연결)';
flow.set('pi_ssid', msg.payload);
return msg;"""

TRIM_IP = r"""const s=(msg.payload||'').toString().trim();
msg.payload = (s.split(/\s+/)[0]||'—');
flow.set('pi_lan_ip', msg.payload);
return msg;"""

TRIM_TS_IP = r"""msg.payload = (msg.payload||'').toString().trim() || '—';
flow.set('pi_ts_ip', msg.payload);
return msg;"""

TRIM_WAN_IP = r"""const s=(msg.payload||'').toString().trim();
msg.payload = (s.split(/\s+/)[0]||'—');
flow.set('pi_wan_ip', msg.payload);
return msg;"""

EXEC_WAN_IP = (
    "/bin/sh -c 'curl -4 -s --max-time 4 https://api.ipify.org 2>/dev/null "
    "|| curl -4 -s --max-time 4 ifconfig.me 2>/dev/null || echo -'"
)

HIDE_PI_TEXT_IDS = (
    "ui_txt_uptime",
    "ui_txt_ssid",
    "ui_txt_ip",
    "ui_txt_ts_ip",
    "ui_txt_pi_host",
    "ui_txt_pi_tick",
)


def _ensure_nodes(flows: list, ids: set) -> None:
    tab = "tab_cronus_dash"
    by_id = {n.get("id"): n for n in flows if isinstance(n, dict)}

    if "fn_pi_system_merge" not in ids:
        flows.append(
            {
                "id": "fn_pi_system_merge",
                "type": "function",
                "z": tab,
                "name": "Pi System merge",
                "func": FN_PI_SYS_MERGE,
                "outputs": 1,
                "timeout": 0,
                "noerr": 0,
                "initialize": "",
                "finalize": "",
                "libs": [],
                "x": 420,
                "y": 220,
                "wires": [["ui_tpl_pi_system"]],
            }
        )
        ids.add("fn_pi_system_merge")

    if "ui_tpl_pi_system" not in ids:
        flows.append(
            {
                "id": "ui_tpl_pi_system",
                "type": "ui_template",
                "z": tab,
                "group": "ui_grp_pi",
                "name": "Pi System 카드",
                "order": 1,
                "width": "12",
                "height": "5",
                "format": PI_FMT,
                "storeOutMessages": True,
                "fwdInMessages": False,
                "resendOnRefresh": True,
                "templateScope": "local",
                "className": "",
                "x": 640,
                "y": 220,
                "wires": [[]],
            }
        )
        ids.add("ui_tpl_pi_system")

    if "exec_wan_ip" not in ids:
        inj = by_id.get("inj_sys_10s") or {}
        flows.append(
            {
                "id": "exec_wan_ip",
                "type": "exec",
                "z": tab,
                "command": EXEC_WAN_IP,
                "addpay": False,
                "append": "",
                "useSpawn": False,
                "timer": "",
                "winHide": False,
                "oldrc": False,
                "name": "Pi WAN IP",
                "x": int(inj.get("x", 200)) + 200,
                "y": int(inj.get("y", 200)) + 80,
                "wires": [[], ["fn_trim_wan_ip"]],
            }
        )
        ids.add("exec_wan_ip")

    if "fn_trim_wan_ip" not in ids:
        flows.append(
            {
                "id": "fn_trim_wan_ip",
                "type": "function",
                "z": tab,
                "name": "wan ip 정리",
                "func": TRIM_WAN_IP,
                "outputs": 1,
                "timeout": 0,
                "noerr": 0,
                "initialize": "",
                "finalize": "",
                "libs": [],
                "x": int(inj.get("x", 200)) + 360,
                "y": int(inj.get("y", 200)) + 80,
                "wires": [["fn_pi_system_merge"]],
            }
        )
        ids.add("fn_trim_wan_ip")


def patch_file(path: Path) -> list[str]:
    if not path.is_file() or not PI_FMT:
        return []
    flows = json.loads(path.read_text(encoding="utf-8-sig"))
    ids = {n.get("id") for n in flows if isinstance(n, dict)}
    changed: list[str] = []
    _ensure_nodes(flows, ids)

    trim_map = {
        "fn_trim_uptime": TRIM_UPTIME,
        "fn_trim_ssid": TRIM_SSID,
        "fn_trim_ip": TRIM_IP,
        "fn_trim_ts_ip": TRIM_TS_IP,
        "fn_trim_wan_ip": TRIM_WAN_IP,
    }
    for n in flows:
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        if nid in trim_map and n.get("func") != trim_map[nid]:
            n["func"] = trim_map[nid]
            changed.append(nid)
        if nid == "fn_pi_system_merge" and n.get("func") != FN_PI_SYS_MERGE:
            n["func"] = FN_PI_SYS_MERGE
            n["wires"] = [["ui_tpl_pi_system"]]
            changed.append(nid)
        if nid == "ui_tpl_pi_system":
            n["format"] = PI_FMT
            n["width"] = "12"
            n["height"] = "5"
            n["order"] = 1
            n["group"] = "ui_grp_pi"
            changed.append(nid)
        if nid == "fn_cf_arduino_wifi_tele" and n.get("func") != FN_ARDU_WIFI_STORE:
            n["func"] = FN_ARDU_WIFI_STORE
            changed.append(nid)
        if nid in HIDE_PI_TEXT_IDS:
            if n.get("width") != 0:
                n["width"] = 0
                changed.append(f"hide:{nid}")
        if nid == "ui_grp_pi" and n.get("name") != "System (Pi : ida)":
            n["name"] = "System (Pi : ida)"
            changed.append(nid)

    inj = next((n for n in flows if isinstance(n, dict) and n.get("id") == "inj_sys_10s"), None)
    if inj and isinstance(inj.get("wires"), list) and inj["wires"]:
        w0 = inj["wires"][0]
        for extra in ("exec_wan_ip", "fn_pi_system_merge"):
            if extra not in w0:
                w0.append(extra)
                changed.append(f"inj→{extra}")
        route = "fn_pi_status_route"
        if route in w0:
            idx = w0.index(route)
            rnode = next((n for n in flows if n.get("id") == route), None)
            if rnode and isinstance(rnode.get("wires"), list) and len(rnode["wires"]) > 1:
                execs = rnode["wires"][1]
                if isinstance(execs, list) and "exec_wan_ip" not in execs:
                    execs.append("exec_wan_ip")
                    changed.append("route→exec_wan_ip")

    for n in flows:
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        if nid in ("fn_trim_uptime", "fn_trim_ssid", "fn_trim_ip", "fn_trim_ts_ip", "fn_trim_wan_ip"):
            w = n.get("wires") or [[]]
            if w and "fn_pi_system_merge" not in (w[0] or []):
                w[0] = list(w[0] or []) + ["fn_pi_system_merge"]
                n["wires"] = w
                changed.append(f"{nid}→merge")

    if changed:
        path.write_text(
            json.dumps(flows, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    return [f"{path.name}:{c}" for c in changed]


def main() -> int:
    if not PI_FMT:
        raise SystemExit("missing scripts/_pi_system_fmt.txt")
    all_c: list[str] = []
    for fp in FLOW_FILES:
        all_c.extend(patch_file(fp))
    if not all_c:
        print("WARN patch_dashboard_pi_system_layout: no changes")
        return 1
    print("OK patch_dashboard_pi_system_layout:", ", ".join(sorted(set(all_c))[:16]), "...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
