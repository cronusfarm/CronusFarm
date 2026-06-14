#!/usr/bin/env bash
# Pi DB schedule_rule → R4 USB serial SCHED_JSON (bridge API — DB lock 충돌 방지)
set -eu
(set -o pipefail 2>/dev/null) && set -o pipefail || true

DEVICE_ID="${CRONUSFARM_DEVICE_ID:-cronusfarm-01}"
BRIDGE="${CRONUSFARM_BRIDGE_URL:-http://127.0.0.1:18766}"

export CRONUSFARM_R4_CMD_TRANSPORT="${CRONUSFARM_R4_CMD_TRANSPORT:-serial}"

for attempt in 1 2 3; do
  if out=$(curl -fsS -m 120 \
    "${BRIDGE}/api/schedule/sync_device?device_id=${DEVICE_ID}" 2>&1); then
    echo "$out"
    exit 0
  fi
  echo "WARN SCHED sync attempt $attempt: $out" >&2
  sleep 2
done
exit 1
