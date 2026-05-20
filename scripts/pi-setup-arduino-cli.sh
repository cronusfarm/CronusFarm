#!/bin/bash
# pi-setup-arduino-cli.sh
# Pi에 arduino-cli 설치 + R4(renesas)/R3(avr) 보드 + 필수 라이브러리 설치
# 최초 1회만 실행

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[setup]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }

if command -v arduino-cli &>/dev/null; then
    warn "arduino-cli 이미 설치됨: $(arduino-cli version)"
else
    log "arduino-cli 설치 중..."
    curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh \
        | BINDIR=/usr/local/bin sudo sh
    log "arduino-cli 설치 완료: $(arduino-cli version)"
fi

arduino-cli config init --overwrite 2>/dev/null || true

log "보드 매니저 URL 설정..."
arduino-cli config add board_manager.additional_urls \
    https://downloads.arduino.cc/packages/package_renesas_boards_index.json 2>/dev/null || true

log "보드 인덱스 업데이트 중..."
arduino-cli core update-index

log "Arduino AVR (UNO R3) 코어 설치..."
arduino-cli core install arduino:avr

log "Arduino Renesas UNO (R4 WiFi) 코어 설치..."
arduino-cli core install arduino:renesas_uno

log "라이브러리 설치 중..."
arduino-cli lib install "PubSubClient"
arduino-cli lib install "WiFiS3"
arduino-cli lib install "LiquidCrystal"
arduino-cli lib install "U8g2"
arduino-cli lib install "DHT sensor library"
arduino-cli lib install "Adafruit Unified Sensor"
arduino-cli lib install "ArduinoJson"

if ! groups dooly | grep -q dialout; then
    log "dooly 사용자를 dialout 그룹에 추가..."
    sudo usermod -aG dialout dooly
    warn "재로그인 후 포트 권한 적용됩니다."
fi

log "=== arduino-cli 설정 완료 ==="
echo ""
echo "설치된 코어:"
arduino-cli core list
echo ""
echo "설치된 라이브러리 (주요):"
arduino-cli lib list 2>/dev/null | grep -E "PubSubClient|LiquidCrystal|ArduinoJson|DHT" || true