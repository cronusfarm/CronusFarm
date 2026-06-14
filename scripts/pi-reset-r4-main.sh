#!/usr/bin/env bash
# [레거시] 이름은 reset 이지만 실제 동작은 R4 업로드입니다.
# 소프트 리셋만: pi-reset-r4.sh 또는 Windows resetcode.ps1
# 업로드: upcode.sh / upcode.ps1 / pi-upload-r4.sh
set -euo pipefail
ROOT="${CRONUS_ROOT:-$HOME/CronusFarm}"
exec bash "$ROOT/scripts/pi-upload-r4.sh" "$ROOT/arduino/CronusFarm"