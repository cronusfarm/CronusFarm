#!/bin/bash
# pi-arduino-upload.sh
# Pi에서 arduino-cli로 R4(CronusFarm), R3(CronusFarmPanel) 컴파일 및 업로드
# 사용: bash pi-arduino-upload.sh <arduino_root> [--auto-port]

set -euo pipefail

ARDUINO_ROOT="${1:-/home/dooly/CronusFarm/arduino}"
AUTO_PORT=false
[[ "${2:-}" == "--auto-port" ]] && AUTO_PORT=true

R4_SKETCH="$ARDUINO_ROOT/CronusFarm"
R3_SKETCH="$ARDUINO_ROOT/CronusFarmPanel"

R4_FQBN="arduino:renesas_uno:unor4wifi"
PANEL_FQBN="arduino:avr:mega"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[upload]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
err()  { echo -e "${RED}[error]${NC} $*"; exit 1; }

if ! command -v arduino-cli &>/dev/null; then
    err "arduino-cli 미설치. pi-setup-arduino-cli.sh 를 먼저 실행하세요."
fi

detect_port() {
    local fqbn="$1"
    local port=""
    if $AUTO_PORT; then
        port=$(arduino-cli board list 2>/dev/null \
            | grep -i "$(echo $fqbn | cut -d: -f3)" \
            | awk '{print $1}' | head -1)
    fi
    echo "$port"
}

R4_PORT_DEFAULT="/dev/ttyACM0"
R3_PORT_DEFAULT="/dev/ttyACM1"

log "연결된 Arduino 보드:"
arduino-cli board list 2>/dev/null || warn "board list 조회 실패"

log "=== R4 (Arduino UNO R4 WiFi) 컴파일 중... ==="
arduino-cli compile --fqbn "$R4_FQBN" --warnings none "$R4_SKETCH"
log "R4 컴파일 완료"

R4_PORT=$(detect_port "$R4_FQBN")
R4_PORT="${R4_PORT:-$R4_PORT_DEFAULT}"

if [[ ! -e "$R4_PORT" ]]; then
    warn "R4 포트 $R4_PORT 없음. 업로드 스킵."
else
    log "R4 업로드 -> $R4_PORT"
    arduino-cli upload --fqbn "$R4_FQBN" --port "$R4_PORT" "$R4_SKETCH"
    log "R4 업로드 완료 ($R4_PORT)"
fi

log "=== Panel (Trigorilla/Mega2560 / CronusFarmPanel) 컴파일 중... ==="
arduino-cli compile --fqbn "$PANEL_FQBN" --warnings none "$R3_SKETCH"
log "Panel 컴파일 완료"

PANEL_PORT=$(detect_port "$PANEL_FQBN")
PANEL_PORT="${PANEL_PORT:-$R3_PORT_DEFAULT}"

if [[ ! -e "$PANEL_PORT" ]]; then
    warn "Panel 포트 $PANEL_PORT 없음. 업로드 스킵."
else
    log "Panel 업로드 -> $PANEL_PORT"
    arduino-cli upload --fqbn "$PANEL_FQBN" --port "$PANEL_PORT" "$R3_SKETCH"
    log "Panel 업로드 완료 ($PANEL_PORT)"
fi

log "=== 모든 Arduino 업로드 완료 ==="