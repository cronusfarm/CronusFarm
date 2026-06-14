#!/bin/bash
# Pi 시스템 타임존 → Asia/Seoul (CronusFarm RTC·24h 그래프·tele 시각 정합)
set -euo pipefail
if [[ "${EUID:-0}" -ne 0 ]]; then
  echo "sudo 로 실행: sudo bash $0" >&2
  exit 1
fi
timedatectl set-timezone Asia/Seoul
timedatectl set-ntp true
echo "=== timedatectl ==="
timedatectl status
echo "OK: timezone Asia/Seoul"
