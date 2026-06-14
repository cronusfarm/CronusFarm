#!/usr/bin/env bash
#
# CronusFarm 패널 시간동기(systemd) 설치/활성화
#
# 사용:
#   sudo bash ./pi-install-panel-time-sync-service.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_SRC="$ROOT/scripts/pi-panel-time-sync.service"
UNIT_DST="/etc/systemd/system/cronusfarm-panel-time-sync.service"

if [[ ! -f "$UNIT_SRC" ]]; then
  echo "[error] unit 파일이 없습니다: $UNIT_SRC" >&2
  exit 1
fi

install -m 0644 "$UNIT_SRC" "$UNIT_DST"
systemctl daemon-reload
systemctl enable cronusfarm-panel-time-sync.service
systemctl restart cronusfarm-panel-time-sync.service

echo "[ok] enabled + restarted: cronusfarm-panel-time-sync.service"
systemctl --no-pager --full status cronusfarm-panel-time-sync.service || true

