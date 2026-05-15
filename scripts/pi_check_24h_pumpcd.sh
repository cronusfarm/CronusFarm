#!/usr/bin/env bash
set -euo pipefail
echo "=== sensor series 24h ==="
curl -s "http://127.0.0.1/farm/cronusfarm-sqlite/api/sensor/series?device_id=cronusfarm-01&zone=phw3988&hours=24" | head -c 400
echo ""
echo "=== chart.js ==="
curl -s -o /dev/null -w "chart_static HTTP %{http_code}\n" http://127.0.0.1/cronusfarm-static/vendor/chart.umd.min.js
DB="${HOME}/.node-red/cronusfarm.sqlite"
if [[ -f "$DB" ]]; then
  echo "=== sensor_reading 24h ==="
  sqlite3 "$DB" "SELECT COUNT(*), MIN(ts_ms), MAX(ts_ms) FROM sensor_reading WHERE zone='phw3988' AND ts_ms > (strftime('%s','now')*1000 - 86400000);"
  echo "=== tele pump_c/d 24h ==="
  sqlite3 "$DB" "SELECT channel_key, COUNT(*), SUM(state) FROM tele_channel_fact WHERE channel_key LIKE 'pump_c%' OR channel_key LIKE 'pump_d%' AND ts_ms > (strftime('%s','now')*1000 - 86400000) GROUP BY channel_key;"
  echo "=== tele pump_c1 last 5 ==="
  sqlite3 "$DB" "SELECT datetime(ts_ms/1000,'unixepoch','localtime'), state FROM tele_channel_fact WHERE channel_key='pump_c1' ORDER BY ts_ms DESC LIMIT 5;"
fi
