#!/bin/bash
# Pi에서 실행: UNO R4 WiFi 업로드(포트 스왑 내성)
# - R4는 1200bps touch reset 후 /dev/ttyACM* 번호가 바뀔 수 있어,
#   arduino-cli 내부 업로더(bossac)가 "기존 포트"만 잡고 실패하는 경우가 있습니다.
# - 이 스크립트는 1200bps touch → 재연결된 ttyACM 포트를 다시 찾은 뒤 bossac으로 업로드합니다.
#
# 사용:
#   ./pi-upload-r4.sh [/path/to/arduino/CronusFarm] [/dev/ttyACM? 또는 /dev/serial/by-id/...]
#
set -euo pipefail

SKETCH_DIR="${1:-/home/dooly/CronusFarm/arduino/CronusFarm}"
PORT_HINT="${2:-}"
FQBN="arduino:renesas_uno:unor4wifi"

if ! command -v arduino-cli >/dev/null 2>&1; then
  echo "arduino-cli 없음" >&2
  exit 1
fi

if [[ ! -d "$SKETCH_DIR" ]]; then
  echo "스케치 폴더 없음: $SKETCH_DIR" >&2
  exit 1
fi

pick_r4_port() {
  local want="${1:-}"
  if [[ -n "$want" ]]; then
    # by-id 같은 심볼릭이면 실제 ttyACM으로 해석
    if [[ -L "$want" ]]; then
      readlink -f "$want"
      return 0
    fi
    echo "$want"
    return 0
  fi

  # board list에서 R4 FQBN으로 매칭
  local p
  p="$(arduino-cli board list 2>/dev/null | grep -F "$FQBN" | head -n 1 | sed -E 's/[[:space:]].*$//')"
  if [[ -n "$p" ]]; then
    echo "$p"
    return 0
  fi

  # /dev/serial/by-id 우선
  if [[ -d /dev/serial/by-id ]]; then
    p="$(ls -1 /dev/serial/by-id/* 2>/dev/null | grep -E 'UNO_WiFi_R4|UNO.*R4|usb-Arduino_UNO_WiFi_R4' | head -n 1)"
    if [[ -n "$p" ]]; then
      readlink -f "$p"
      return 0
    fi
  fi

  # 폴백
  p="$(ls -1 /dev/ttyACM* 2>/dev/null | head -n 1)"
  echo "$p"
}

find_bossac() {
  local base="$HOME/.arduino15/packages/arduino/tools/bossac"
  if [[ -d "$base" ]]; then
    local x
    x="$(ls -1 "$base"/*/bossac 2>/dev/null | sort -V | tail -n 1)"
    if [[ -n "$x" && -x "$x" ]]; then
      echo "$x"
      return 0
    fi
  fi
  return 1
}

echo "SKETCH_DIR=$SKETCH_DIR"
echo "PORT_HINT=$PORT_HINT"

# 1) 컴파일(바이너리 경로 고정)
OUT="/tmp/cf_r4_build"
rm -rf "$OUT"
mkdir -p "$OUT"
arduino-cli core update-index >/dev/null
arduino-cli core install "arduino:renesas_uno" >/dev/null
arduino-cli lib install "ArduinoMqttClient" >/dev/null || true
arduino-cli compile --fqbn "$FQBN" --output-dir "$OUT" "$SKETCH_DIR"

BIN="$OUT/CronusFarm.ino.bin"
if [[ ! -f "$BIN" ]]; then
  echo "바이너리 없음: $BIN" >&2
  exit 2
fi

BOSSAC="$(find_bossac || true)"
if [[ -z "$BOSSAC" ]]; then
  echo "bossac 경로를 찾지 못했습니다." >&2
  exit 3
fi

echo "BIN=$BIN"
echo "BOSSAC=$BOSSAC"

# 2) 현재 R4 포트 탐지
PRE="$(pick_r4_port "$PORT_HINT")"
if [[ -z "$PRE" || ! -e "$PRE" ]]; then
  echo "R4 포트를 찾지 못했습니다." >&2
  arduino-cli board list || true
  exit 4
fi
echo "PRE=$PRE"

# 3) 1200bps touch reset
set +e
stty -F "$PRE" 1200 2>/dev/null
set -e
sleep 0.2

# 4) 재연결된 포트 찾기 (by-id 타깃이 바뀌는 경우 + ACM 스왑)
NEW="$PRE"
for _ in $(seq 1 80); do
  CUR="$(pick_r4_port "")"
  if [[ -n "$CUR" && -e "$CUR" && "$CUR" != "$PRE" ]]; then
    NEW="$CUR"
    break
  fi
  sleep 0.1
done
echo "NEW=$NEW"

DEV="$(basename "$NEW")"
echo "USE_DEV=$DEV"

# 5) bossac 업로드(ttyACM 이름만 받음)
"$BOSSAC" -d --port="$DEV" -U -e -w "$BIN" -R
echo "DONE"

