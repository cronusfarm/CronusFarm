#!/usr/bin/env bash
# MQTT 안정화 일괄 적용 (Pi에서 실행)
# 1) nodered env  2) mosquitto  3) secrets.h LAN only  4) R4 업로드  5) 검증
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRETS="${CRONUSFARM_SECRETS:-$ROOT/arduino/CronusFarm/secrets.h}"
DEVICE_ID="${CRONUSFARM_DEVICE_ID:-cronusfarm-01}"

log() { echo "[$(date +%H:%M:%S)] $*"; }

log "=== [1/5] Node-RED env (SQLite + MQTT 쿨다운) ==="
bash "$ROOT/scripts/pi-apply-nodered-cronusfarm-env.sh"

log "=== [2/5] Mosquitto 0.0.0.0:1883 ==="
sudo bash "$ROOT/scripts/pi-mosquitto-apply-cronusfarm-conf.sh"

log "=== [3/5] secrets.h — DuckDNS 브로커 제거 (LAN만) ==="
if [[ ! -f "$SECRETS" ]]; then
  echo "ERROR: secrets.h 없음: $SECRETS" >&2
  exit 1
fi
if grep -q 'cronusfarm\.duckdns\.org' "$SECRETS"; then
  bak="${SECRETS}.bak.$(date +%Y%m%d%H%M%S)"
  cp -a "$SECRETS" "$bak"
  python3 - "$SECRETS" <<'PY'
import re, sys
path = sys.argv[1]
text = open(path, encoding="utf-8", errors="replace").read()
new = re.sub(
    r'\s*\{\s*"cronusfarm\.duckdns\.org"\s*,\s*51883\s*\}\s*,?',
    '',
    text,
    count=1,
)
if new == text:
    new = "\n".join(
        ln for ln in text.splitlines()
        if "cronusfarm.duckdns.org" not in ln
    ) + ("\n" if text.endswith("\n") else "")
open(path, "w", encoding="utf-8", newline="\n").write(new)
PY
  log "DuckDNS 브로커 제거 (백업: $bak)"
else
  log "이미 DuckDNS 브로커 없음"
fi
grep -A3 'MQTT_BROKERS' "$SECRETS" | head -6 || true

log "=== [4/5] R4 펌웨어 업로드 ==="
bash "$ROOT/scripts/pi-upload-r4.sh"

log "=== [5/5] 연결 검증 ==="
sleep 8
echo "--- api/time/status ---"
curl -fsS -m 8 "http://127.0.0.1:18766/api/time/status?device_id=${DEVICE_ID}" \
  | python3 -m json.tool 2>/dev/null || true
echo "--- status retain (3s) ---"
timeout 4 mosquitto_sub -h 127.0.0.1 -p 1883 \
  -t "cronusfarm/${DEVICE_ID}/status" -C 1 -W 3 2>/dev/null || echo "status: timeout"
echo "--- tele 샘플 (6s) ---"
timeout 6 mosquitto_sub -h 127.0.0.1 -p 1883 \
  -t "cronusfarm/${DEVICE_ID}/tele" -v 2>/dev/null | head -3 || echo "tele: timeout"
if [[ -x "$ROOT/scripts/_pi_mqtt_diag.sh" ]]; then
  bash "$ROOT/scripts/_pi_mqtt_diag.sh" || true
fi
log "=== 완료 ==="
