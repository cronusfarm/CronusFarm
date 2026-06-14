#!/bin/bash
# Pi에서 실행: /etc/cronusfarm/nodered-telegram.env 의 날씨 키 줄바꿈/중복을 정리
set -euo pipefail

F=/etc/cronusfarm/nodered-telegram.env
if [[ ! -f "$F" ]]; then
  echo "없음: $F" >&2
  exit 1
fi

sudo bash -lc "
  set -e
  sed -i '/^nCRONUSFARM_WEATHER_LAT=/d' '$F' || true
  grep -q '^CRONUSFARM_WEATHER_LAT=' '$F' || echo 'CRONUSFARM_WEATHER_LAT=' >> '$F'
  grep -q '^CRONUSFARM_WEATHER_LON=' '$F' || echo 'CRONUSFARM_WEATHER_LON=' >> '$F'
  grep -q '^CRONUSFARM_WEATHER_NAME=' '$F' || echo 'CRONUSFARM_WEATHER_NAME=' >> '$F'
  chmod 600 '$F'
  tail -n 8 '$F'
"

