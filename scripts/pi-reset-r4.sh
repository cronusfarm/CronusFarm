#!/usr/bin/env bash
# Pi: UNO R4 WiFi 소프트 리셋만 (1200bps touch — compile/upload 없음)
#
# upcode / pi-upload-r4.sh 는 컴파일+업로드. 이 스크립트는 펌웨어 재시작만 합니다.
#
# 사용:
#   ./pi-reset-r4.sh
#   ./pi-reset-r4.sh /dev/ttyACM1
#   ./pi-reset-r4.sh /dev/serial/by-id/usb-Arduino_UNO_WiFi_R4_...
#
set -eu
(set -o pipefail 2>/dev/null) && set -o pipefail || true
PORT_HINT="${1:-}"
FQBN="arduino:renesas_uno:unor4wifi"
WAIT_SEC="${CRONUSFARM_RESET_WAIT_SEC:-12}"

pick_r4_port() {
  local want="${1:-}"
  if [[ -n "$want" ]]; then
    if [[ -L "$want" ]]; then
      readlink -f "$want"
      return 0
    fi
    echo "$want"
    return 0
  fi

  local p
  p="$(arduino-cli board list 2>/dev/null | grep -F "$FQBN" | head -n 1 | sed -E 's/[[:space:]].*$//' || true)"
  if [[ -n "$p" ]]; then
    echo "$p"
    return 0
  fi

  if [[ -d /dev/serial/by-id ]]; then
    p="$(ls -1 /dev/serial/by-id/* 2>/dev/null | grep -E 'UNO_WiFi_R4|UNO.*R4|usb-Arduino_UNO_WiFi_R4' | head -n 1 || true)"
    if [[ -n "$p" ]]; then
      readlink -f "$p"
      return 0
    fi
  fi

  p="$(ls -1 /dev/ttyACM* 2>/dev/null | head -n 1 || true)"
  echo "$p"
}

release_port() {
  local port="$1"
  [[ -n "$port" && -e "$port" ]] || return 0
  if command -v fuser >/dev/null 2>&1; then
    sudo -n fuser -k "$port" 2>/dev/null || fuser -k "$port" 2>/dev/null || true
    sleep 0.5
  fi
}

if ! command -v arduino-cli >/dev/null 2>&1; then
  echo "arduino-cli 없음 (포트 탐지용)" >&2
  exit 1
fi

PRE="$(pick_r4_port "$PORT_HINT")"
if [[ -z "$PRE" || ! -e "$PRE" ]]; then
  echo "R4 시리얼 포트를 찾지 못했습니다." >&2
  arduino-cli board list 2>/dev/null || true
  exit 2
fi

echo "R4 소프트 리셋 (1200 touch, 업로드 없음)"
echo "PRE=$PRE"

release_port "$PRE"

set +e
stty -F "$PRE" 1200 2>/dev/null || true
set -e
sleep 2

NEW="$PRE"
for _ in $(seq 1 120); do
  CUR="$(pick_r4_port "")"
  if [[ -n "$CUR" && -e "$CUR" ]]; then
    NEW="$CUR"
    break
  fi
  sleep 0.1
done

echo "NEW=$NEW"
echo "부팅 대기 ${WAIT_SEC}s (BOOT_SCHED_GRACE·WiFi·MQTT)…"
sleep "$WAIT_SEC"

if command -v arduino-cli >/dev/null 2>&1; then
  arduino-cli board list 2>/dev/null | grep -F "$FQBN" || true
fi

echo "완료: R4 소프트 리셋 (펌웨어는 기존 플래시 그대로)"
