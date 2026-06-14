#!/usr/bin/env bash
# R4 리셋 없이 WiFi 프로비저닝 — DTR 리셋 방지 + 부팅 로그 대기
# pi-reset 직후에는 이 스크립트 대신: pi-reset-r4.sh && sleep 90 && 본 스크립트
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${CRONUSFARM_R4_SERIAL:-/dev/ttyACM2}"
WAIT="${CRONUSFARM_WIFI_BOOT_WAIT_SEC:-90}"

sudo systemctl stop cronusfarm-mqtt-watch 2>/dev/null || true
echo "[safe] mqtt-watch 중지 (선택)"
echo "[safe] port=$PORT boot_wait=${WAIT}s"
export CRONUSFARM_WIFI_BOOT_WAIT_SEC="$WAIT"
exec python3 "$ROOT/scripts/pi-serial-wifi-provision.py" --port "$PORT"
