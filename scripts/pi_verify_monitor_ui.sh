#!/usr/bin/env bash
set -euo pipefail
F="${1:-$HOME/.node-red/flows.json}"
python3 - <<'PY' "$F"
import json, sys
path = sys.argv[1]
d = json.load(open(path, encoding="utf-8"))
by = {n["id"]: n for n in d if isinstance(n, dict) and n.get("id")}
print("nodes", len(d))
print("led_b2_order", by.get("ui_tpl_state_led_b2", {}).get("order"))
print("led_b2_wire", by.get("sw_route_state", {}).get("wires", [[]])[7] if "sw_route_state" in by else None)
print("24h_tpl", "ui_tpl_phw_water_24h" in by)
print("hive", "d7013a5209d5fe9b" in json.dumps(d))
print("brokers", [n.get("id") for n in d if n.get("type") == "mqtt-broker"])
PY
code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1/farm/cronusfarm-sqlite/api/sensor/series?hours=1" || echo err)
echo "sensor_series HTTP $code"
