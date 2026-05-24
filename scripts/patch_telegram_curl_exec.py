# -*- coding: utf-8 -*-
"""Node.js가 api.telegram.org 에 연결 실패(Pi) → curl exec 로 Telegram HTTP 대체."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAB = "b1c5a1f1d7a2a3a1"
FILES = (
    "flows_cronusfarm_dashboard.json",
    "flows_cronusfarm_mqtt.json",
    "CronusFarm_NodeRED_flow.json",
)

FN_CURL = r"""// Telegram: Node https 타임아웃 회피 (curl) — settings.js functionGlobalContext.child_process 필요
const cp = global.get('child_process');
if (!cp) {
  node.error('child_process 없음 — pi-nodered-patch-child-process-context.sh 실행');
  return null;
}
const url = (msg.url || '').toString();
if (!url) { return null; }
const method = (msg.method || 'GET').toString().toUpperCase();
const headers = msg.headers || {};
let hdr = '';
for (const k of Object.keys(headers)) {
  hdr += ' -H ' + JSON.stringify(k + ': ' + headers[k]);
}
let body = '';
if (method !== 'GET' && msg.payload != null && msg.payload !== '') {
  const pl = typeof msg.payload === 'string' ? msg.payload : JSON.stringify(msg.payload);
  body = ' -d ' + JSON.stringify(pl);
}
const cmd = 'curl -s -m 90 -X ' + method + hdr + body + ' ' + JSON.stringify(url);
try {
  msg.payload = cp.execSync(cmd, { encoding: 'utf8', maxBuffer: 10 * 1024 * 1024 }).toString();
} catch (e) {
  msg.payload = JSON.stringify({ ok: false, error: String(e.message || e) });
}
return msg;"""


def patch_flow(path: Path) -> None:
    if not path.is_file():
        return
    flows = json.loads(path.read_text(encoding="utf-8-sig"))
    ids = {n.get("id") for n in flows if isinstance(n, dict)}

    def upsert(node: dict) -> None:
        nid = node["id"]
        for i, n in enumerate(flows):
            if isinstance(n, dict) and n.get("id") == nid:
                flows[i] = {**n, **node}
                return
        flows.append(node)

    for cid, cname, cwires in (
        ("cf_fn_tg_curl_get", "Telegram curl GET", [["cf_fn_tg_dispatch"]]),
        ("cf_fn_tg_curl_send", "Telegram curl send", [[]]),
    ):
        upsert(
            {
                "id": cid,
                "type": "function",
                "z": TAB,
                "name": cname,
                "func": FN_CURL,
                "outputs": 1,
                "timeout": 0,
                "noerr": 0,
                "initialize": "",
                "finalize": "",
                "libs": [],
                "x": 520,
                "y": 920,
                "wires": cwires,
            }
        )

    for n in flows:
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        if nid == "cf_fn_tg_pollurl":
            n["wires"] = [["cf_fn_tg_curl_get"]]
        if nid in ("cf_fn_tg_curl_get", "cf_fn_tg_curl_send"):
            n["func"] = FN_CURL
        if nid == "cf_fn_tg_curl_get":
            n["wires"] = [["cf_fn_tg_dispatch"]]
        if nid == "cf_fn_tg_curl_send":
            n["wires"] = [[]]
        if nid == "cf_fn_tg_curl":
            n["disabled"] = True
            n["wires"] = [[]]
        if nid == "cf_hreq_tg_getup":
            n["wires"] = [[]]
        if nid == "cf_fn_tg_dispatch":
            w = n.get("wires") or [[], [], []]
            while len(w) < 3:
                w.append([])
            w[0] = ["cf_fn_tg_curl_send"]
            n["wires"] = w
        if nid == "cf_fn_tg_weather_fmt":
            n["wires"] = [["cf_fn_tg_curl_send"]]
        if nid == "cf_fn_tg_ollama_reply":
            n["wires"] = [["cf_fn_tg_curl_send"]]
        if nid in ("cf_hreq_tg_getup", "cf_hreq_tg_sendmsg"):
            n["wires"] = [[]]

    path.write_text(json.dumps(flows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("OK", path.name)


def main() -> None:
    for name in FILES:
        patch_flow(ROOT / "nodered" / name)


if __name__ == "__main__":
    main()
