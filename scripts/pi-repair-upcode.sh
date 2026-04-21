#!/bin/bash
# ida(Pi)에서 실행: upcode 스크립트 없으면 생성 + ~/.bashrc 복구(잘린 alias·경로 줄 제거)
# 사용: bash ~/CronusFarm/scripts/pi-repair-upcode.sh
set -eu
SCRIPT_DIR="${HOME}/CronusFarm/scripts"
mkdir -p "$SCRIPT_DIR"

echo "=== 0) 스크립트 없으면 생성(있으면 유지) ==="
if [[ ! -f "$SCRIPT_DIR/upcode.sh" ]]; then
  cat > "$SCRIPT_DIR/upcode.sh" <<'UPCODE_CREATE'
#!/bin/bash
# Pi 셸용: Windows 의 upcode.ps1 과 동일 역할(이 저장소에서 compile+upload)
# 사용: ~/CronusFarm/scripts/upcode.sh
#        ~/CronusFarm/scripts/upcode.sh /dev/ttyACM0
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKETCH="$ROOT/arduino/CronusFarm"
BUILD="$ROOT/scripts/pi-arduino-build.sh"
export FQBN="${FQBN:-arduino:renesas_uno:unor4wifi}"
if [[ ! -f "$BUILD" ]]; then
  echo "없음: $BUILD (CronusFarm 클론 경로 확인)" >&2
  exit 1
fi
if [[ ! -d "$SKETCH" ]]; then
  echo "없음: $SKETCH" >&2
  exit 1
fi
exec bash "$BUILD" "$SKETCH" "${1:-}"
UPCODE_CREATE
  chmod +x "$SCRIPT_DIR/upcode.sh"
  echo "생성: $SCRIPT_DIR/upcode.sh"
fi

if [[ ! -f "$SCRIPT_DIR/pi-arduino-build.sh" ]]; then
  cat > "$SCRIPT_DIR/pi-arduino-build.sh" <<'BUILD_CREATE'
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

if ! command -v arduino-cli >/dev/null 2>&1; then
  echo "arduino-cli가 없습니다. 설치: curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh" >&2
  exit 1
fi

arduino-cli version
arduino-cli core update-index
arduino-cli core install arduino:renesas_uno
arduino-cli lib install "ArduinoMqttClient"

if [[ -z "$PORT" ]]; then
  PORT="$(arduino-cli board list | awk '/ttyACM/{print $1; exit}' || true)"
fi
if [[ -z "$PORT" ]]; then
  PORT="/dev/ttyACM0"
fi
echo "업로드 포트: $PORT"

arduino-cli compile -j 4 --fqbn "$FQBN" "$SKETCH_DIR"

if [[ -e "$PORT" ]] && command -v fuser >/dev/null 2>&1; then
  echo "시리얼 점유 해제 시도: $PORT"
  sudo -n fuser -k "$PORT" 2>/dev/null || fuser -k "$PORT" 2>/dev/null || true
  sleep 1
fi

arduino-cli upload -p "$PORT" --fqbn "$FQBN" "$SKETCH_DIR"
echo "완료: compile + upload"
BUILD_CREATE
  chmod +x "$SCRIPT_DIR/pi-arduino-build.sh"
  echo "생성: $SCRIPT_DIR/pi-arduino-build.sh"
fi

chmod +x "$SCRIPT_DIR/upcode.sh"
chmod +x "$SCRIPT_DIR/pi-arduino-build.sh"

BRC="${HOME}/.bashrc"
touch "$BRC"
cp -a "$BRC" "${BRC}.bak.repair.$(date +%s)"

echo "=== 1) ~/.bashrc 에서 upcode/upcod 관련 줄 제거(잘린 경로 줄 포함) ==="
grep -v 'alias upcode' "$BRC" \
  | grep -v 'alias upcod=' \
  | grep -v '# --- CronusFarm upcode' \
  | grep -v '# --- end CronusFarm upcode' \
  | grep -v 'CronusFarm/scripts/upcode.sh' \
  > /tmp/.bashrc.repair.$$
{
  echo ""
  echo "# --- CronusFarm upcode (auto) ---"
  echo "alias upcode='bash ${HOME}/CronusFarm/scripts/upcode.sh'"
  echo "alias upcod='bash ${HOME}/CronusFarm/scripts/upcode.sh'"
  echo "# --- end CronusFarm upcode ---"
} >> /tmp/.bashrc.repair.$$

echo "=== 2) 합친 ~/.bashrc 문법 검사 ==="
if ! bash -n /tmp/.bashrc.repair.$$ 2>/tmp/bashrc.err; then
  echo "합친 결과도 문법 오류입니다. 백업으로 되돌리세요:" >&2
  cat /tmp/bashrc.err >&2
  rm -f /tmp/.bashrc.repair.$$
  exit 1
fi
mv /tmp/.bashrc.repair.$$ "$BRC"
echo "OK"

ls -la "$SCRIPT_DIR/upcode.sh" "$SCRIPT_DIR/pi-arduino-build.sh"
echo ""
echo "완료.  source ~/.bashrc  후  type upcode"
