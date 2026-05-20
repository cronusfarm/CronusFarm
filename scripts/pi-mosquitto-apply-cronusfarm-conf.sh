#!/usr/bin/env bash
# Pi에서 실행: CronusFarm용 Mosquitto가 0.0.0.0:1883 에 바인드되도록 설정 후 재시작.
# 사용: 저장소 루트에서 sudo bash scripts/pi-mosquitto-apply-cronusfarm-conf.sh
set -euo pipefail

if [[ "${EUID:-0}" -ne 0 ]]; then
  exec sudo bash "$0" "$@"
fi

CONF="/etc/mosquitto/conf.d/cronusfarm.conf"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SRC="${REPO_ROOT}/deploy/mosquitto/conf.d/cronusfarm.conf"

if [[ -f "$SRC" ]]; then
  install -m 0644 "$SRC" "$CONF"
  echo "[pi-mosquitto] 설치: $CONF (저장소 파일 복사)"
else
  cat >"$CONF" <<'MQTT_EOF'
# CronusFarm — 모든 IPv4 인터페이스(LAN·Tailscale 등)에서 MQTT 수신
# log_* 는 mosquitto.conf 에 있음 — 중복 시 기동 실패
listener 1883 0.0.0.0
allow_anonymous true
MQTT_EOF
  chmod 0644 "$CONF"
  echo "[pi-mosquitto] 설치: $CONF (내장 스니펫)"
fi

systemctl enable mosquitto 2>/dev/null || true
systemctl restart mosquitto

if ss -ltnp 2>/dev/null | grep -q ':1883'; then
  echo "[pi-mosquitto] OK — 1883 리스닝 확인:"
  ss -ltnp | grep ':1883' || true
else
  echo "[pi-mosquitto] WARN — ss 로 1883 확인 실패. journalctl -u mosquitto -n 50 로 로그 확인." >&2
  echo "         Debian 기본 설정과 listener 가 겹치면 /etc/mosquitto/mosquitto.conf 및 conf.d 를 정리하세요." >&2
fi
