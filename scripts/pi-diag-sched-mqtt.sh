#!/usr/bin/env bash
# Pi: MQTT cmd·tele·스케줄 불일치 빠른 진단
set -eu
DB=/home/dooly/.node-red/cronusfarm.sqlite
DEV=cronusfarm-01
echo "=== recent cmd (15) ==="
sqlite3 "$DB" "SELECT datetime(ts_ms/1000,'unixepoch','localtime'), substr(payload,1,100) FROM mqtt_cmd_log WHERE device_id='$DEV' ORDER BY ts_ms DESC LIMIT 15;"
echo "=== live tele ==="
timeout 6 mosquitto_sub -h 127.0.0.1 -p 1883 -t "cronusfarm/${DEV}/tele" -C 1 -W 5 || echo "(tele timeout)"
echo "=== sched diag ==="
python3 ~/CronusFarm/scripts/_pi_diag_sched_live.py || true
