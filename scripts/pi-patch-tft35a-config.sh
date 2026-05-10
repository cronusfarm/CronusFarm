#!/bin/bash
# Pi에서 실행: tft35a 줄의 오타 파라미터(렌=20)를 주석으로 보존하고 정상 dtoverlay 줄을 둠.
set -euo pipefail
CFG="/boot/firmware/config.txt"
BAK="/boot/firmware/config.txt.bak-$(date +%Y%m%d%H%M%S)"
OLD_LINE='dtoverlay=tft35a,rotate=270,speed=12000000,렌=20'

if [[ $EUID -ne 0 ]]; then
  echo "sudo 로 실행하세요: sudo bash $0" >&2
  exit 1
fi

cp -a "$CFG" "$BAK"
echo "백업: $BAK"

python3 - "$CFG" <<'PY'
import sys
path = sys.argv[1]
old = "dtoverlay=tft35a,rotate=270,speed=12000000,렌=20"
with open(path, "r", encoding="utf-8") as f:
    t = f.read()
if old not in t:
    print("ERR: 기대 문자열 없음:", repr(old), file=sys.stderr)
    sys.exit(2)
block = (
    "# dtoverlay=tft35a,rotate=270,speed=12000000,렌=20\n"
    "# (과거 활성값 보존. '렌=' 는 tft35a overlay 알려진 파라미터가 아님 → 아래 줄 사용)\n"
    "dtoverlay=tft35a,rotate=270,speed=12000000\n"
)
t = t.replace(old, block, 1)
with open(path, "w", encoding="utf-8") as f:
    f.write(t)
print("OK: config.txt 패치됨")
PY

grep -n tft35a "$CFG"
