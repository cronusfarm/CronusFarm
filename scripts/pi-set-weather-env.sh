#!/usr/bin/env bash
# Pi: Open-Meteo 날씨 좌표 + KMA 격자 + 텔레그램 Ollama env
set -euo pipefail
ENV="/etc/cronusfarm/nodered-telegram.env"
LAT="${CRONUSFARM_WEATHER_LAT:-37.54294}"
LON="${CRONUSFARM_WEATHER_LON:-127.12733}"
NAME="${CRONUSFARM_WEATHER_NAME:-서울 강동 천호동 농장}"
NX="${CRONUSFARM_KMA_NX:-71}"
NY="${CRONUSFARM_KMA_NY:-127}"

sudo touch "$ENV"
OLLAMA_EN="${CRONUSFARM_OLLAMA_ENABLED:-1}"
OLLAMA_MODEL="${CRONUSFARM_OLLAMA_MODEL:-gemma:2b}"
OLLAMA_HOST="${CRONUSFARM_OLLAMA_HOST:-http://127.0.0.1:11434}"
for kv in \
  "CRONUSFARM_WEATHER_LAT=$LAT" \
  "CRONUSFARM_WEATHER_LON=$LON" \
  "CRONUSFARM_WEATHER_NAME=$NAME" \
  "CRONUSFARM_KMA_NX=$NX" \
  "CRONUSFARM_KMA_NY=$NY" \
  "CRONUSFARM_OLLAMA_ENABLED=$OLLAMA_EN" \
  "CRONUSFARM_OLLAMA_MODEL=$OLLAMA_MODEL" \
  "CRONUSFARM_OLLAMA_HOST=$OLLAMA_HOST"; do
  key="${kv%%=*}"
  val="${kv#*=}"
  sudo sed -i "/^${key}=/d" "$ENV"
  printf '%s=%q\n' "$key" "$val" | sudo tee -a "$ENV" >/dev/null
done
sudo chmod 600 "$ENV"
KMA_DROP="/etc/systemd/system/nodered.service.d/cronusfarm-kma.conf"
if [[ -f "$KMA_DROP" ]]; then
  sudo sed -i "s/^Environment=CRONUSFARM_KMA_NX=.*/Environment=CRONUSFARM_KMA_NX=$NX/" "$KMA_DROP"
  sudo sed -i "s/^Environment=CRONUSFARM_KMA_NY=.*/Environment=CRONUSFARM_KMA_NY=$NY/" "$KMA_DROP"
  sudo systemctl daemon-reload
  echo "OK systemd: $KMA_DROP NX=$NX NY=$NY"
fi
echo "OK weather env: LAT=$LAT LON=$LON NAME=$NAME NX=$NX NY=$NY"
sudo grep -E '^CRONUSFARM_(WEATHER|KMA_N|OLLAMA_)' "$ENV" || true
