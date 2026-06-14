#!/bin/bash
# Pi: 모니터·MQTT·설정 SPA 패치 일괄 적용 (git 불필요 — Windows에서 pi-sync-patches.ps1 로 복사)
set -eu
ROOT="${HOME}/CronusFarm"
cd "$ROOT"

run_py() {
  local f="$1"
  if [[ ! -f "$f" ]]; then
    echo "ERROR: 없음 — git pull 또는 PC에서 push 후 다시 시도: $f" >&2
    exit 1
  fi
  echo "=== $(basename "$f") ==="
  python3 "$f"
}

run_py scripts/patch_nodered_mqtt_broker_local.py
run_py scripts/patch_settings_spa.py
run_py scripts/patch_monitor_ui_requests.py
run_py scripts/patch_dashboard_monitor_layout.py
run_py scripts/patch_dashboard_monitor_extended.py
run_py scripts/patch_dashboard_usb_primary.py
run_py scripts/patch_dashboard_monitor_status_oneline.py
run_py scripts/patch_dashboard_monitor_status_kma.py 2>/dev/null || true

echo "=== merge + Node-RED ==="
python3 scripts/merge_nodered_deploy.py --use-split
bash scripts/pi-nodered-apply-merged.sh nodered/merged-deploy.json

echo "=== dashboard index.html → ~/.node-red ==="
if [[ -f nodered/dashboard/index.html ]]; then
  mkdir -p "${HOME}/.node-red/dashboard"
  cp -f nodered/dashboard/index.html "${HOME}/.node-red/dashboard/index.html"
fi

echo "=== sqlite bridge (자동 RTC 등) ==="
sudo systemctl restart cronusfarm-sqlite-bridge 2>/dev/null || true
sudo systemctl restart nodered 2>/dev/null || true

echo "OK pi-apply-monitor-patches.sh 완료"
