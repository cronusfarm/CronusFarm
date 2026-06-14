#!/bin/bash
# R4 USB 시리얼 포트 자동 맞춤 + 데몬 재시작 (ACM2 고정 오류 복구)
set -eu
ROOT="${HOME}/CronusFarm"
ENV_DIR="/etc/cronusfarm"
ENV_FILE="${ENV_DIR}/r4-serial.env"
sudo mkdir -p "$ENV_DIR"
PORT=""
for p in /dev/ttyACM1 /dev/ttyACM0 /dev/ttyACM2; do
  if [[ -e "$p" ]]; then
    PORT="$p"
    break
  fi
done
if [[ -z "$PORT" ]]; then
  echo "ERROR: /dev/ttyACM* 없음 — R4 USB 연결 확인" >&2
  exit 1
fi
echo "CRONUSFARM_R4_SERIAL=${PORT}" | sudo tee "$ENV_FILE" >/dev/null
echo "CRONUSFARM_R4_CMD_TRANSPORT=serial" | sudo tee -a /etc/cronusfarm/bridge.env 2>/dev/null || true
sudo cp -f "$ROOT/deploy/systemd/cronusfarm-r4-serial.service" /etc/systemd/system/ 2>/dev/null || true
sudo systemctl daemon-reload
sudo systemctl restart cronusfarm-r4-serial cronusfarm-sqlite-bridge
sleep 2
curl -fsS -m 5 -X POST "http://127.0.0.1:18767/r4/cmd" \
  -H 'Content-Type: application/json' \
  -d '{"device_id":"cronusfarm-01","payload":"rtc_local='$(date +%Y%m%d%H%M%S)'"}' && echo " RTC cmd OK" || echo "WARN: RTC cmd fail"
echo "OK pi-fix-r4-serial-port PORT=${PORT}"
