#!/bin/bash
# Pi에서 실행: TFT SPI 패널이 하얀 빈 화면만 보일 때, tty1 콘솔 대비(글자 색)와 clear 실패 내성 보강.
# 사용법: sudo bash ~/CronusFarm/scripts/pi-patch-tft-dashboard-visible.sh
set -euo pipefail
SRC="${1:-/usr/local/bin/tft-dashboard.sh}"
BAK="${SRC}.bak-$(date +%Y%m%d%H%M%S)"

if [[ $EUID -ne 0 ]]; then
  echo "sudo 로 실행하세요." >&2
  exit 1
fi
[[ -f "$SRC" ]] || { echo "없음: $SRC" >&2; exit 1; }

cp -a "$SRC" "$BAK"
echo "백업: $BAK"

python3 - "$SRC" <<'PY'
import sys
path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
    t = f.read()

# set -e 이면 clear/journalctl 일시 실패 시 루프가 죽을 수 있음
t = t.replace("set -euo pipefail", "set -uo pipefail", 1)

old_while = """while true; do
  clear
  echo "=== TFT 서비스 모니터 (VT1) ==="
"""

new_while = """while true; do
  # SPI TFT: 밝은 배경 + 흰 글자 조합이면 “하얀 빈 화면”처럼 보임 → 대비 강화 + 소등 끔
  setterm -blank 0 -powersave off </dev/tty1 >/dev/tty1 2>/dev/null || true
  setterm --foreground white --background blue --clear all </dev/tty1 >/dev/tty1 2>/dev/null || true
  clear || true
  echo "=== TFT 서비스 모니터 (VT1) ==="
"""

if old_while not in t:
    print("ERR: 예상 블록 없음(수동으로 tft-dashboard.sh 확인)", file=sys.stderr)
    sys.exit(2)
t = t.replace(old_while, new_while, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(t)
print("OK: 패치 반영:", path)
PY

systemctl restart tft-dashboard.service
sleep 1
systemctl --no-pager status tft-dashboard.service | head -15
echo "※ 로컬에서 TFT만 볼 때: sudo chvt 1 (TTY1을 화면에 올림)"
