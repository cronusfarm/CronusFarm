#!/bin/bash
# Pi: MQTT 끊김 진단 (mosquitto·status 로그·연결)
set -euo pipefail
DB="${CRONUSFARM_SQLITE:-/home/dooly/.node-red/cronusfarm.sqlite}"
echo "=== mosquitto ==="
systemctl is-active mosquitto 2>/dev/null || true
journalctl -u mosquitto --since "48 hours ago" --no-pager 2>/dev/null | grep -iE 'disconnect|error|warning|Client' | tail -20 || true
echo ""
echo "=== mqtt_status_log (최근 20) ==="
if [[ -f "$DB" ]]; then
  sqlite3 "$DB" "SELECT datetime(ts_ms/1000,'unixepoch','localtime'), payload FROM mqtt_status_log WHERE device_id='cronusfarm-01' ORDER BY ts_ms DESC LIMIT 20;" 2>/dev/null || true
fi
echo ""
echo "=== tele_sample 간격 (최근 10) ==="
if [[ -f "$DB" ]]; then
  sqlite3 "$DB" "SELECT datetime(ts_ms/1000,'unixepoch','localtime'), length(raw) FROM tele_sample WHERE device_id='cronusfarm-01' ORDER BY ts_ms DESC LIMIT 10;" 2>/dev/null || true
fi
echo ""
echo "=== wlan ==="
iw dev wlan0 link 2>/dev/null | head -6 || true
echo ""
echo "=== mosquitto clients (sub 2s) ==="
timeout 2 mosquitto_sub -h 127.0.0.1 -t '$SYS/broker/clients/connected' -C 1 2>/dev/null || true
