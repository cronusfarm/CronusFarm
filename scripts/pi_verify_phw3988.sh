#!/usr/bin/env bash
set -euo pipefail
F="${1:-$HOME/.node-red/flows.json}"
python3 - <<'PY' "$F"
import json, sys
path = sys.argv[1]
d = json.load(open(path, encoding="utf-8"))
blob = json.dumps(d).lower()
by = {n["id"]: n for n in d if isinstance(n, dict) and n.get("id")}
print("nodes", len(d))
print("hivemq", "hivemq" in blob or "d7013a5209d5fe9b" in by)
print("sf_3team", "sf_3team" in blob)
print("tuya_ip", by.get("8ed219bf73293e78", {}).get("deviceIp"))
print("mqtt_topic", by.get("4fd2979510810d5f", {}).get("topic"))
print("sqlite_fn", "cf_phw_fn_sqlite01" in by)
print("gauges", sum(1 for n in d if n.get("type") == "ui_gauge" and n.get("group") == "ui_grp_gh_data"))
PY
code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:18766/health || echo "err")
echo "bridge_health HTTP $code"
if command -v sqlite3 >/dev/null 2>&1 && [[ -f "$HOME/.node-red/cronusfarm.sqlite" ]]; then
  sqlite3 "$HOME/.node-red/cronusfarm.sqlite" \
    "SELECT COUNT(*) FROM sensor_reading WHERE source='phw3988' AND ts_ms > (strftime('%s','now')*1000 - 3600000);"
fi
