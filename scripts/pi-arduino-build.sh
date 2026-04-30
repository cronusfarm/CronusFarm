#!/bin/bash
# 라즈베리파이에서 직접 실행: 의존성 확인 후 컴파일·업로드
# 사용: ./pi-arduino-build.sh [SKETCH_DIR] [PORT]
# 예: ./pi-arduino-build.sh /home/dooly/CronusFarm/arduino/CronusFarm /dev/ttyACM0

set -euo pipefail

FQBN="${FQBN:-arduino:renesas_uno:unor4wifi}"
if [[ -n "${1:-}" ]]; then
  SKETCH_DIR="$1"
else
  SKETCH_DIR="$(cd "$(dirname "$0")/../arduino/CronusFarm" && pwd)"
fi
PORT="${2:-}"

pick_port() {
  local want="$1"

  if [[ -n "$want" ]]; then
    echo "$want"
    return 0
  fi

  # 안정 경로 우선: /dev/serial/by-id/*
  if [[ -d /dev/serial/by-id ]]; then
    if [[ "$FQBN" == *"avr"* ]]; then
      # Trigorilla/Mega2560는 보통 USB-UART(예: CP2102)로 ttyUSB*에 붙습니다.
      local p
      p="$(ls -1 /dev/serial/by-id/* 2>/dev/null | grep -E 'CP210|cp210|USB_to_UART|usb-.*CP210' | head -n 1 || true)"
      if [[ -n "$p" ]]; then
        echo "$p"
        return 0
      fi
    else
      # UNO R4 WiFi는 보통 ttyACM*에 붙습니다.
      local p
      # 주의: UNO R4는 by-id에 CMSIS-DAP(디버그 인터페이스)와 CDC(ttyACM) 둘 다 보일 수 있습니다.
      # 업로드는 보통 CDC(ttyACM) 쪽(if00)으로 진행해야 "Device unsupported"를 피할 수 있습니다.
      p="$(ls -1 /dev/serial/by-id/* 2>/dev/null | grep -E 'UNO_WiFi_R4|UNO.*R4|usb-Arduino_UNO_WiFi_R4' | grep -E 'if00|ttyACM' | head -n 1 || true)"
      if [[ -n "$p" ]]; then
        echo "$p"
        return 0
      fi
    fi
  fi

  # 폴백: 타입별 기본 탐지
  if [[ "$FQBN" == *"avr"* ]]; then
    want="$(ls -1 /dev/ttyUSB* 2>/dev/null | head -n 1 || true)"
    if [[ -n "$want" ]]; then
      echo "$want"
      return 0
    fi
  fi

  want="$(ls -1 /dev/ttyACM* 2>/dev/null | head -n 1 || true)"
  if [[ -n "$want" ]]; then
    echo "$want"
    return 0
  fi

  # 마지막 폴백(기존 동작 유지)
  echo "/dev/ttyACM0"
}

if ! command -v arduino-cli >/dev/null 2>&1; then
  echo "arduino-cli가 없습니다. 설치: curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh" >&2
  exit 1
fi

arduino-cli version
arduino-cli core update-index
# FQBN 예: arduino:renesas_uno:unor4wifi | arduino:avr:uno → 앞 두 토큰으로 코어 패키지 설치
CORE_REF="$(echo "$FQBN" | cut -d: -f1,2)"
if [[ -z "$CORE_REF" || "$CORE_REF" == "$FQBN" || "$CORE_REF" != *:* ]]; then
  echo "FQBN 형식 오류: $FQBN (예: arduino:avr:uno 또는 arduino:renesas_uno:unor4wifi)" >&2
  exit 1
fi
arduino-cli core install "$CORE_REF"
if [[ "$FQBN" == *"renesas"* ]]; then
  arduino-cli lib install "ArduinoMqttClient"
fi
# UNO R3 패널(CronusFarmPanel) — SD 카드 라이브러리
if [[ "$FQBN" == *"avr"* ]]; then
  arduino-cli lib install "SD"
fi

if [[ -z "$PORT" ]]; then
  PORT="$(pick_port "")"
fi
if [[ -z "$PORT" ]]; then
  PORT="/dev/ttyACM0"
fi
echo "업로드 포트: $PORT"

arduino-cli compile -j 4 --fqbn "$FQBN" "$SKETCH_DIR"

# 업로드는 USB 재인식/드라이버 타임아웃으로 간헐 실패할 수 있어 재시도합니다.
# - AVR(Mega/Uno): ttyUSB* 흔들림(EMI/허브) 흡수
# - Renesas(R4): 1200bps 터치 후 포트가 잠깐 끊겼다가 다시 뜸
for attempt in 1 2 3; do
  # 포트가 아직 안 뜨면 잠깐 대기
  for i in 1 2 3 4 5; do
    if [[ -e "$PORT" ]]; then
      break
    fi
    echo "대기: 포트가 아직 없습니다($PORT) ..."
    sleep 1
    PORT="$(pick_port "$PORT")"
  done

  # 업로드 직전: 점유 프로세스 종료(가능할 때만)
  if [[ -e "$PORT" ]] && command -v fuser >/dev/null 2>&1; then
    echo "시리얼 점유 해제 시도: $PORT"
    sudo -n fuser -k "$PORT" 2>/dev/null || fuser -k "$PORT" 2>/dev/null || true
    sleep 1
  fi

  set +e
  arduino-cli upload -p "$PORT" --fqbn "$FQBN" "$SKETCH_DIR"
  ec=$?
  set -e
  if [[ $ec -eq 0 ]]; then
    echo "완료: compile + upload"
    exit 0
  fi

  echo "경고: 업로드 실패(ec=$ec) — 재시도 $attempt/3"
  sleep 2
  # 실패 후 포트가 바뀌었을 수 있어 재탐지
  PORT="$(pick_port "")"
  echo "재탐지 포트: $PORT"
done

echo "오류: 업로드 3회 재시도 모두 실패" >&2
exit 1
