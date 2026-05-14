#!/usr/bin/env bash
set -euo pipefail

# Influx 토큰은 systemd drop-in에서만 읽음(표준출력에 토큰 전체를 찍지 않음)
CONF="/etc/systemd/system/nodered.service.d/cronusfarm-influx.conf"
if [[ ! -f "$CONF" ]]; then
  echo "missing $CONF" >&2
  exit 1
fi

TOKEN="$(grep -E '^Environment=CRONUSFARM_INFLUX_TOKEN=' "$CONF" | head -n1 | sed 's/^Environment=CRONUSFARM_INFLUX_TOKEN=//')"
ORG="$(grep -E '^Environment=CRONUSFARM_INFLUX_ORG=' "$CONF" | head -n1 | sed 's/^Environment=CRONUSFARM_INFLUX_ORG=//')"
BUCKET="$(grep -E '^Environment=CRONUSFARM_INFLUX_BUCKET=' "$CONF" | head -n1 | sed 's/^Environment=CRONUSFARM_INFLUX_BUCKET=//')"

if [[ -z "$TOKEN" || -z "$ORG" || -z "$BUCKET" ]]; then
  echo "failed to parse ORG/BUCKET/TOKEN from $CONF" >&2
  exit 1
fi

echo "org=$ORG bucket=$BUCKET"

echo "--- buckets"
influx bucket list --org "$ORG" --token "$TOKEN" --hide-headers | awk '{print $1}' | head -n 20

echo "--- measurements (last 7d, first 30)"
influx query --org "$ORG" --token "$TOKEN" "
import \"influxdata/influxdb/schema\"
schema.measurements(bucket: \"$BUCKET\")
" | head -n 40

echo "--- tele fields sample (last 2h)"
influx query --org "$ORG" --token "$TOKEN" "
from(bucket: \"$BUCKET\")
  |> range(start: -2h)
  |> filter(fn: (r) => r._measurement == \"tele\")
  |> keep(columns: [\"_field\"])
  |> distinct(column: \"_field\")
  |> sort()
" | head -n 80

echo "--- kma_temp points (last 48h, max 5 rows)"
influx query --org "$ORG" --token "$TOKEN" "
from(bucket: \"$BUCKET\")
  |> range(start: -48h)
  |> filter(fn: (r) => r._measurement == \"tele\" and r._field == \"kma_temp\")
  |> limit(n: 5)
" | head -n 30
