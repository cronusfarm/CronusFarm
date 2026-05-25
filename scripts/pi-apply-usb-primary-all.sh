#!/usr/bin/env bash
# Pi 일괄: git pull → USB serial 설치 → R4 업로드 → 복구 → MQTT 진단
set -eu
(set -o pipefail 2>/dev/null) && set -o pipefail || true

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export CRONUSFARM_SKIP_R4_RESET="${CRONUSFARM_SKIP_R4_RESET:-0}"

log() { echo "[$(date +%H:%M:%S)] $*"; }

log "=== git pull ==="
git fetch origin 2>/dev/null || true
git checkout feature/r4-usb-serial-primary 2>/dev/null || true
git pull --ff-only origin feature/r4-usb-serial-primary 2>/dev/null || git pull --ff-only || true

for f in "$ROOT"/scripts/*.sh "$ROOT"/scripts/*.py; do
  [[ -f "$f" ]] && tr -d '\r' <"$f" >"$f.lf" && mv "$f.lf" "$f" && chmod +x "$f" 2>/dev/null || true
done

log "=== USB serial primary 설치 ==="
bash "$ROOT/scripts/pi-install-r4-serial-primary.sh"

log "=== R4 펌웨어 업로드 (수 분) ==="
bash "$ROOT/scripts/pi-upload-r4.sh" || { log "WARN 업로드 실패"; exit 1; }

log "=== 부팅 대기 120s ==="
sleep 120

log "=== USB 복구·RTC·auto ==="
bash "$ROOT/scripts/pi-recover-r4-usb.sh"

log "=== MQTT 진단 (근본원인 참고) ==="
if [[ -f "$ROOT/scripts/_pi_mqtt_diag.sh" ]]; then
  bash "$ROOT/scripts/_pi_mqtt_diag.sh" 2>&1 | tail -n 40 || true
fi

log "=== Node-RED /ui 개발환경 반영 ==="
if [[ -f "$ROOT/nodered/merged-deploy.json" ]]; then
  cp "$ROOT/nodered/merged-deploy.json" "$HOME/.node-red/flows.json"
  sudo systemctl restart nodered.service 2>/dev/null || true
  sleep 8
fi

log "=== health ==="
curl -fsS -m 5 http://127.0.0.1:18767/health && echo
curl -fsS -m 5 "http://127.0.0.1:18766/api/time/status?device_id=cronusfarm-01" && echo

log "DONE"
