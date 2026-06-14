# -*- coding: utf-8 -*-
"""Pi 도메인(Tailscale · DuckDNS) — Pi tick 과 같이 한 줄(전체 너비) 표시."""
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

FN_PI_HOST = r"""const ts = (env.get('CRONUSFARM_PI_HOST') || 'ida.mango-larch.ts.net').toString().trim();
const duck = (env.get('CRONUSFARM_PI_DUCKDNS') || 'cronusfarm.duckdns.org').toString().trim();
const sep = ' \u00b7 ';
const parts = [];
if (ts) parts.push(ts);
if (duck && duck !== ts) parts.push(duck);
msg.payload = parts.length ? parts.join(sep) : ('ida.mango-larch.ts.net' + sep + 'cronusfarm.duckdns.org');
return msg;"""


def patch_file(path: Path) -> list[str]:
    if not path.is_file():
        return []
    flows = json.loads(path.read_text(encoding="utf-8-sig"))
    changed: list[str] = []

    for n in flows:
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        if nid == "fn_pi_host" and n.get("func") != FN_PI_HOST:
            n["func"] = FN_PI_HOST
            changed.append(nid)
        if nid == "ui_txt_pi_host":
            if n.get("width") != 12:
                n["width"] = 12
                changed.append("ui_txt_pi_host:width")
            if n.get("height") != 1:
                n["height"] = 1
                changed.append("ui_txt_pi_host:height")
            if n.get("layout") != "row-spread":
                n["layout"] = "row-spread"
                changed.append("ui_txt_pi_host:layout")
            if n.get("label") != "Pi 도메인":
                n["label"] = "Pi 도메인"
            if n.get("order") != 5:
                n["order"] = 5

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
        print("WARN patch_dashboard_pi_domain_oneline: no changes")
        return 1
    print("OK patch_dashboard_pi_domain_oneline:", ", ".join(sorted(set(all_c))[:16]), "...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
