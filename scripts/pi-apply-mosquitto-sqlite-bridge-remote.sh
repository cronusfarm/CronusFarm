#!/usr/bin/env bash
# Pi에서 실행됨 (SSH로 호출). $HOME 에 업로드된 설정 파일을 시스템 경로에 설치한다.
# 사전: 호스트에 ~/cronusfarm_apply_mosquitto.conf, ~/cronusfarm_sqlite_bridge.service.new 가 있어야 함.

set -euo pipefail

M="${HOME}/cronusfarm_apply_mosquitto.conf"
S="${HOME}/cronusfarm_sqlite_bridge.service.new"

if [[ ! -f "$M" ]]; then
  echo "[error] 없음: $M (먼저 PC에서 pi-apply-mosquitto-sqlite-bridge.ps1 실행)" >&2
  exit 1
fi
if [[ ! -f "$S" ]]; then
  echo "[error] 없음: $S" >&2
  exit 1
fi

# SQLite 브리지 기본 DB 경로 상위 디렉터리
mkdir -p "${HOME}/.node-red"

comment_listener_port() {
  local f="$1"
  local port="$2"
  [[ -f "$f" ]] || return 0
  if sudo grep -qE "^[[:space:]]*listener[[:space:]]+${port}([[:space:]]|$)" "$f" 2>/dev/null; then
    echo "[Pi] Mosquitto 포트 충돌 방지 — listener ${port} 주석: $f"
    sudo cp -a "$f" "${f}.bak.cronusfarm-$(date +%s)"
    sudo sed -i "/^[[:space:]]*listener[[:space:]]\\+${port}/s/^/# CronusFarm-was-/" "$f"
  fi
}

echo "[Pi] Mosquitto 패키지 확인..."
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y mosquitto mosquitto-clients

echo "[Pi] 기존 Mosquitto listener 1883/51883 정리(중복 시 기동 실패 방지)..."
shopt -s nullglob
for f in /etc/mosquitto/conf.d/*.conf; do
  [[ "$(basename "$f")" == "cronusfarm.conf" ]] && continue
  comment_listener_port "$f" 1883
  comment_listener_port "$f" 51883
done
if [[ -f /etc/mosquitto/mosquitto.conf ]]; then
  comment_listener_port /etc/mosquitto/mosquitto.conf 1883
  comment_listener_port /etc/mosquitto/mosquitto.conf 51883
fi

echo "[Pi] Mosquitto drop-in 설치 (listener 1883 0.0.0.0 — log_* 없음)..."
sudo install -m 0644 "$M" /etc/mosquitto/conf.d/cronusfarm.conf
sudo systemctl enable mosquitto 2>/dev/null || true
if ! sudo systemctl restart mosquitto; then
  echo "[warn] mosquitto 재시작 실패 — 아래 로그 확인" >&2
  sudo journalctl -u mosquitto -n 35 --no-pager >&2 || true
fi

echo "[Pi] SQLite 브리지 systemd 설치..."
sudo install -m 0644 "$S" /etc/systemd/system/cronusfarm-sqlite-bridge.service
sudo systemctl daemon-reload
sudo systemctl enable cronusfarm-sqlite-bridge
if ! sudo systemctl restart cronusfarm-sqlite-bridge; then
  echo "[warn] cronusfarm-sqlite-bridge 재시작 실패" >&2
  sudo journalctl -u cronusfarm-sqlite-bridge -n 35 --no-pager >&2 || true
fi

if command -v ufw >/dev/null 2>&1; then
  echo "[Pi] ufw 18766/tcp 허용(있으면)..."
  sudo ufw allow 18766/tcp comment 'cronusfarm-sqlite-bridge' 2>/dev/null || true
  sudo ufw allow 1883/tcp comment 'cronusfarm-mqtt' 2>/dev/null || true
fi

sleep 2

echo ""
echo "--- 리스닝(:1883, :18766) ---"
ss -ltnp 2>/dev/null | grep -E ':1883|:18766' || echo "(ss 결과 없음)"
echo "--- 서비스 상태 ---"
systemctl --no-pager is-active mosquitto 2>/dev/null || true
systemctl --no-pager is-active cronusfarm-sqlite-bridge 2>/dev/null || true
echo "--- 브리지 health ---"
if curl -s -S --max-time 5 -f http://127.0.0.1:18766/health; then
  echo ""
else
  echo "(curl 실패)"
  echo "--- cronusfarm-sqlite-bridge 최근 로그 ---"
  sudo journalctl -u cronusfarm-sqlite-bridge -n 40 --no-pager || true
fi
echo ""
echo "[Pi] 적용 스크립트 완료."
