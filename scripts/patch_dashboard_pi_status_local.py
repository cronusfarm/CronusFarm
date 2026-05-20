# -*- coding: utf-8 -*-
"""
로컬(Windows) Node-RED: Pi System 카드가 systemctl exec 실패로 전부 offline 되는 문제.

- inj_sys_10s → fn_pi_status_route
  - 로컬: fn_pi_remote_probe (Tailscale HTTP/TCP)
  - Pi/Linux: 기존 exec_uptime … exec_srv_* 유지
- fn_pi_host: env CRONUSFARM_PI_HOST 반영
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

EXEC_TARGETS = [
    "exec_uptime",
    "exec_ssid",
    "exec_ip",
    "exec_ts_ip",
    "exec_srv_nodered",
    "exec_srv_mosquitto",
]

# Node-RED function 샌드박스에는 process 가 없음 → env 만 사용 (로컬 PS1 이 CRONUSFARM_LOCAL_DEV=1 설정)
FN_PI_STATUS_ROUTE = """const localDev = ['1', 'true', 'yes'].includes(
  String(env.get('CRONUSFARM_LOCAL_DEV') || '').toLowerCase()
);
if (localDev) {
  return [msg, null];
}
return [null, msg];"""

FN_PI_REMOTE_PROBE = """const piHost = String(env.get('CRONUSFARM_PI_HOST') || 'ida.mango-larch.ts.net').replace(/\\/+$/, '');
const mqttPort = parseInt(String(env.get('CRONUSFARM_MQTT_PORT') || '1883'), 10) || 1883;
const nginxPort = parseInt(String(env.get('CRONUSFARM_NGINX_PORT') || '1880'), 10) || 1880;
const nrPort = parseInt(String(env.get('CRONUSFARM_NR_PORT') || '51882'), 10) || 51882;
const bridgePort = parseInt(String(env.get('CRONUSFARM_SQLITE_BRIDGE_PORT') || '18766'), 10) || 18766;
const http = require('http');
const net = require('net');

function httpOk(port, path) {
  return new Promise((resolve) => {
    const req = http.request({
      hostname: piHost,
      port,
      path: path || '/',
      method: 'GET',
      timeout: 5000
    }, (res) => {
      resolve(res.statusCode >= 200 && res.statusCode < 500);
    });
    req.on('error', () => resolve(false));
    req.setTimeout(5000, () => { req.destroy(); resolve(false); });
    req.end();
  });
}

function tcpOk(port) {
  return new Promise((resolve) => {
    const s = net.connect({ host: piHost, port, timeout: 5000 }, () => { s.end(); resolve(true); });
    s.on('error', () => resolve(false));
    s.setTimeout(5000, () => { s.destroy(); resolve(false); });
  });
}

(async () => {
  const nrOk = (await httpOk(nginxPort, '/')) || (await httpOk(nrPort, '/'));
  const mqOk = await tcpOk(mqttPort);
  const bridgeOk = await httpOk(bridgePort, '/api/channel/status?device_id=cronusfarm-01&channel=pump_a1');
  const ok = nrOk && mqOk;
  node.send([
    { payload: ok ? '원격 Pi (' + piHost + ') 응답 OK' : '원격 Pi 응답 없음' },
    { payload: ok ? 'Tailscale' : '(미연결)' },
    { payload: piHost },
    { payload: piHost },
    { payload: nrOk ? 'active' : 'inactive' },
    { payload: mqOk ? 'active' : 'inactive' }
  ]);
})().catch((e) => {
  node.warn('fn_pi_remote_probe: ' + e);
  node.send([
    { payload: '원격 Pi 프로브 오류' },
    { payload: '(미연결)' },
    { payload: piHost },
    { payload: piHost },
    { payload: 'inactive' },
    { payload: 'inactive' }
  ]);
});
return null;"""

FN_PI_HOST = """const h = (env.get('CRONUSFARM_PI_HOST') || 'ida.mango-larch.ts.net').toString().trim();
msg.payload = h || 'ida.mango-larch.ts.net';
return msg;"""


def patch() -> None:
    data = json.loads(DASH.read_text(encoding="utf-8-sig"))
    by_id = {n["id"]: n for n in data if isinstance(n, dict) and n.get("id")}

    inj = by_id.get("inj_sys_10s")
    if not inj:
        raise SystemExit("inj_sys_10s 없음")

    ix = int(inj.get("x", 200))
    iy = int(inj.get("y", 200))

    route = by_id.get("fn_pi_status_route")
    if not route:
        route = {
            "id": "fn_pi_status_route",
            "type": "function",
            "z": "tab_cronus_dash",
            "name": "Pi 상태 경로(로컬/피)",
            "func": FN_PI_STATUS_ROUTE,
            "outputs": 2,
            "timeout": 0,
            "noerr": 0,
            "initialize": "",
            "finalize": "",
            "libs": [],
            "x": ix + 120,
            "y": iy,
            "wires": [[], []],
        }
        data.append(route)
    else:
        route["func"] = FN_PI_STATUS_ROUTE
        route["outputs"] = 2

    probe = by_id.get("fn_pi_remote_probe")
    if not probe:
        probe = {
            "id": "fn_pi_remote_probe",
            "type": "function",
            "z": "tab_cronus_dash",
            "name": "Pi 원격 프로브(로컬)",
            "func": FN_PI_REMOTE_PROBE,
            "outputs": 6,
            "timeout": 0,
            "noerr": 0,
            "initialize": "",
            "finalize": "",
            "libs": [],
            "x": ix + 280,
            "y": iy - 40,
            "wires": [[], [], [], [], [], []],
        }
        data.append(probe)
    else:
        probe["func"] = FN_PI_REMOTE_PROBE
        probe["outputs"] = 6

    route["wires"] = [
        ["fn_pi_remote_probe"],
        EXEC_TARGETS,
    ]
    probe["wires"] = [
        ["fn_trim_uptime"],
        ["fn_trim_ssid"],
        ["fn_trim_ip"],
        ["fn_trim_ts_ip"],
        ["fn_trim_nodered"],
        ["fn_trim_mosq"],
    ]

    inj["wires"] = [
        [
            "fn_pi_status_route",
            "fn_pi_tick",
            "fn_pi_host",
        ]
    ]

    host_fn = by_id.get("fn_pi_host")
    if host_fn:
        host_fn["func"] = FN_PI_HOST

    DASH.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print("OK patch_dashboard_pi_status_local")

    merge = ROOT / "scripts" / "merge_nodered_deploy.py"
    if merge.is_file():
        r = subprocess.run([sys.executable, str(merge), "--use-split"], cwd=str(ROOT))
        if r.returncode != 0:
            raise SystemExit("merge 실패")


if __name__ == "__main__":
    patch()
