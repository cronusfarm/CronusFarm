#!/usr/bin/env bash
#
# Pi → Trigorilla Panel 시간 전송(USB Serial)
# - 패널(CronusFarmPanel.ino)이 표시하는 "LCD판넬 환영메세지"의 날짜/시간을 Pi 시각으로 갱신합니다.
#
# 사용:
#   bash ./pi-panel-time-sync.sh /dev/ttyUSB0
#
# 중지: Ctrl+C
#

set -euo pipefail

PORT="${1:-/dev/ttyUSB0}"
BAUD="${BAUD:-115200}"
INTERVAL_SEC="${INTERVAL_SEC:-1}"
START_DELAY_SEC="${START_DELAY_SEC:-2}"

if [[ ! -e "$PORT" ]]; then
  echo "[error] 포트 없음: $PORT" >&2
  exit 1
fi

echo "[info] port=$PORT baud=$BAUD interval=${INTERVAL_SEC}s"

# raw 모드로 설정(에코/개행 변환 방지)
stty -F "$PORT" "$BAUD" raw -echo -echoe -echok -crtscts || true

# 주의: Mega2560 계열은 포트를 열 때 DTR 변화로 리셋될 수 있습니다.
# 파일 리다이렉션(> "$PORT")을 루프마다 하면 매번 리셋될 수 있으니,
# 포트를 1번만 열어둔 상태로 계속 write 합니다.
exec 3>"$PORT"
sleep "$START_DELAY_SEC"

while true; do
  # LCD(HD44780)는 한글/UTF-8 글꼴을 못 찍는 경우가 많아 요일은 영어로 고정합니다.
  dt="$(LC_ALL=C date '+%Y.%m.%d (%a)')"
  tm="$(date '+%H:%M:%S')"
  # 패널 파서: DT:/TM: 라인 사용
  printf 'DT:%s\nTM:%s\n' "$dt" "$tm" >&3
  sleep "$INTERVAL_SEC"
done

