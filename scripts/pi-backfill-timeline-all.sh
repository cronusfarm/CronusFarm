#!/usr/bin/env bash
# Pi: tele_sample → tele_channel_fact 백필 (기본 48h)
set -euo pipefail
HOURS="${1:-48}"
API="http://127.0.0.1:18766/api/channel/backfill"
DEV="${CRONUSFARM_DEVICE_ID:-cronusfarm-01}"
CHS="led_a1,led_a2,pump_a1,pump_a2,fan_a1,fan_a2,led_b1,led_b2,pump_b1,pump_b2,fan_b1,fan_b2,pump_c1,pump_c2,pump_d1,pump_d2"
for ch in $(echo "$CHS" | tr ',' ' '); do
  body=$(printf '{"device_id":"%s","channel_key":"%s","hours":%s}' "$DEV" "$ch" "$HOURS")
  n=$(curl -s -m 120 -X POST -H 'Content-Type: application/json' -d "$body" "$API" | python3 -c "import sys,json; print(json.load(sys.stdin).get('inserted',0))" 2>/dev/null || echo "?")
  echo "$ch inserted=$n"
done
