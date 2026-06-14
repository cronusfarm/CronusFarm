# -*- coding: utf-8 -*-
"""Pi Node-RED MQTT 브로커 → 127.0.0.1 (Tailscale 호스트 루프백 실패·tele 끊김 방지)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MQTT = ROOT / "nodered" / "flows_cronusfarm_mqtt.json"
MERGED = ROOT / "nodered" / "merged-deploy.json"
BROKER_ID = "d6b7f6c1b2b3c4d5"
LOCAL = "127.0.0.1"


def _patch(data: list) -> int:
    n = 0
    for node in data:
        if node.get("type") != "mqtt-broker":
            continue
        if node.get("id") == BROKER_ID or "mosquitto" in (node.get("name") or "").lower():
            if node.get("broker") != LOCAL:
                node["broker"] = LOCAL
                node["name"] = "Mosquitto (Pi localhost)"
                n += 1
    return n


def main() -> int:
    for path in (MQTT, MERGED):
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        c = _patch(data)
        path.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        print(f"OK {path.name}: mqtt-broker → {LOCAL} ({c} nodes)")

    merge = ROOT / "scripts" / "merge_nodered_deploy.py"
    if merge.is_file():
        r = subprocess.run(
            [sys.executable, str(merge), "--use-split"],
            cwd=str(ROOT),
        )
        if r.returncode != 0:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
