#!/usr/bin/env bash
# Pi: cronusfarm.sqlite 스키마·스케줄·수동홀드 요약
set -euo pipefail
DB="${CRONUSFARM_SQLITE_PATH:-/home/dooly/.node-red/cronusfarm.sqlite}"
DEV="${1:-cronusfarm-01}"
echo "DB=$DB device=$DEV"
echo "=== tables ==="
sqlite3 "$DB" "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
echo "=== schema_version ==="
sqlite3 "$DB" "SELECT * FROM schema_version ORDER BY version;"
echo "=== schedule_rule count ==="
sqlite3 "$DB" "SELECT COUNT(*) FROM schedule_rule WHERE device_id='$DEV';"
echo "=== channel_manual_hold ==="
sqlite3 -header -column "$DB" "SELECT channel_key, hold_minutes, datetime(expires_ms/1000,'unixepoch','localtime') exp FROM channel_manual_hold WHERE device_id='$DEV';" 2>/dev/null || echo "(none)"
echo "=== settings_kv (schedule related) ==="
sqlite3 -header -column "$DB" "SELECT key, substr(value,1,80) FROM settings_kv WHERE device_id='$DEV' LIMIT 30;" 2>/dev/null || echo "(none)"
