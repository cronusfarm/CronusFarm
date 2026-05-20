#!/usr/bin/env bash
# Pi에서 채널 ON 유지·MQTT·tele 검증 (cronusfarm-01)
set -euo pipefail
BASE="${CRONUSFARM_VERIFY_BASE:-http://127.0.0.1/farm/cronusfarm-sqlite}"
DEV="${CRONUSFARM_DEVICE_ID:-cronusfarm-01}"
CH="${CRONUSFARM_VERIFY_CH:-led_a1}"

echo "=== status (before) ==="
curl -sf "${BASE}/api/channel/status?device_id=${DEV}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
c=d.get('channels',{}).get('${CH}',{})
print('${CH}', 'state=', c.get('state'), 'auto=', c.get('auto_mode'), 'ts_ms=', c.get('ts_ms'))
"

echo "=== set_manual ON (new_state=1) ==="
curl -sf -X POST "${BASE}/api/channel-action" \
  -H 'Content-Type: application/json' \
  -d "{\"device_id\":\"${DEV}\",\"channel\":\"${CH}\",\"action\":\"set_manual\",\"new_state\":1,\"prev_state\":0,\"hold_minutes\":30}" | python3 -m json.tool

sleep 3
echo "=== status (after manual ON) ==="
curl -sf "${BASE}/api/channel/status?device_id=${DEV}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
c=d.get('channels',{}).get('${CH}',{})
print('${CH}', 'state=', c.get('state'), 'auto=', c.get('auto_mode'))
"

echo "=== schedule now? ==="
curl -sf "${BASE}/api/schedule?device_id=${DEV}&channel=${CH}" | python3 -c "
import json,sys,datetime
d=json.load(sys.stdin)
rules=d.get('rules') or []
print('rules', len(rules))
"
