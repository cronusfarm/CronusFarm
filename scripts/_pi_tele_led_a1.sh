#!/bin/bash
set -e
DB=/home/dooly/.node-red/cronusfarm.sqlite
curl -sf -X POST http://127.0.0.1:18766/api/channel-action \
  -H 'Content-Type: application/json' \
  -d '{"device_id":"cronusfarm-01","channel":"led_a1","action":"set_manual","on":true,"new_state":1,"new_auto":0,"hold_minutes":30}'
echo
sleep 4
RAW=$(sqlite3 "$DB" "SELECT raw FROM tele_sample WHERE device_id='cronusfarm-01' ORDER BY ts_ms DESC LIMIT 1;")
echo "tele_raw_excerpt:"
echo "$RAW" | tr '|' '\n' | grep -E 'led_a1|S:' | head -6
curl -sf 'http://127.0.0.1:18766/api/channel/status?device_id=cronusfarm-01' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['channels']['led_a1'])"
