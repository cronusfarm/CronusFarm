#!/usr/bin/env bash
#
# Pi 또는 개발 PC(레포 체크아웃)에서 실행: CronusFarm/scripts 아래 진단 스크립트를
# Pi 홈의 ~/CronusFarm/scripts/ 에 복사해 둔다.
#
# 사용 (레포 루트에서):
#   bash scripts/pi-install-diagnose-to-home.sh
# 대상 디렉터리만 바꾸려면:
#   bash scripts/pi-install-diagnose-to-home.sh /home/dooly/CronusFarm
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DST="${1:-$HOME/CronusFarm}/scripts"
mkdir -p "$DST"
install -m 0755 "$ROOT/scripts/pi-diagnose-ui.sh" "$DST/"
install -m 0755 "$ROOT/scripts/pi-nodered-ensure-upstream-for-nginx.sh" "$DST/"
echo "[ok] $DST/pi-diagnose-ui.sh"
echo "     bash $DST/pi-diagnose-ui.sh"
