#!/usr/bin/env bash
# /etc/cronusfarm/nodered-telegram.env — CronusFarm Node-RED·mqtt-watch 권장값 병합
# 사용: bash ~/CronusFarm/scripts/pi-apply-nodered-cronusfarm-env.sh
set -euo pipefail

ENV_FILE="${CRONUSFARM_TELEGRAM_ENV:-/etc/cronusfarm/nodered-telegram.env}"

apply_block() {
  local begin="$1" end="$2" body="$3"
  sudo mkdir -p "$(dirname "$ENV_FILE")"
  if [[ -f "$ENV_FILE" ]] && grep -qF "$begin" "$ENV_FILE"; then
    sudo sed -i "/${begin//\//\\/}/,/${end//\//\\/}/d" "$ENV_FILE"
  fi
  {
    echo "$begin"
    echo "$body"
    echo "$end"
  } | sudo tee -a "$ENV_FILE" >/dev/null
}

MARK_SQLITE_BEGIN="# --- CronusFarm SQLite bridge (auto) ---"
MARK_SQLITE_END="# --- end SQLite bridge ---"
SQLITE_BLOCK="# tele/cmd/status → SQLite HTTP 브리지 (Node-RED env.get)
CRONUSFARM_SQLITE_BRIDGE_URL=http://127.0.0.1:18766
# tele DB 샘플 간격(ms). 기본 15000 — 5000 이면 UI·타임라인 반응 빨라짐
CRONUSFARM_SQLITE_MIN_MS=5000"

MARK_COOLDOWN_BEGIN="# --- CronusFarm MQTT alert cooldown (auto) ---"
MARK_COOLDOWN_END="# --- end MQTT alert cooldown ---"
COOLDOWN_BLOCK="# 오프라인 알림 최소 간격 30분 (Node-RED)
CRONUSFARM_TG_OFFLINE_ALERT_MIN_MS=1800000
# retain offline 전용 NR 알림 끄기(선택, 1=끔) — connLineOk+mqtt-watch만
# CRONUSFARM_TG_OFFLINE_ALERT_DISABLE=1
# mqtt-watch: tele 60초 없을 때만, 알림 30분
CRONUSFARM_MQTT_TELE_STALE_SEC=60
CRONUSFARM_MQTT_ALERT_COOLDOWN_SEC=1800
CRONUSFARM_MQTT_RECOVER_NOTIFY=1
# status offline 3분 → R4 USB wifi_set (secrets.h), 재시도 간격 30분
CRONUSFARM_MQTT_AUTO_RECOVER=1
CRONUSFARM_MQTT_AUTO_RECOVER_AFTER_SEC=180
CRONUSFARM_MQTT_AUTO_RECOVER_COOLDOWN_SEC=1800
CRONUSFARM_MQTT_AUTO_RECOVER_NOTIFY=1"

apply_block "$MARK_SQLITE_BEGIN" "$MARK_SQLITE_END" "$SQLITE_BLOCK"
apply_block "$MARK_COOLDOWN_BEGIN" "$MARK_COOLDOWN_END" "$COOLDOWN_BLOCK"

echo "OK: $ENV_FILE"
sudo grep -E '^(CRONUSFARM_SQLITE_|CRONUSFARM_TG_OFFLINE|CRONUSFARM_MQTT_)' "$ENV_FILE" 2>/dev/null || true

sudo systemctl restart nodered 2>/dev/null || true
sudo systemctl restart cronusfarm-mqtt-watch 2>/dev/null || true
echo "restarted nodered + cronusfarm-mqtt-watch"
