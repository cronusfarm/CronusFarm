#!/bin/bash
# Pi에서 설정 SPA + D1 플로우 반영 (git pull 후)
set -eu
ROOT="${HOME}/CronusFarm"
cd "$ROOT"

echo "=== patch_settings_spa (D1 설정 탭 → SPA) ==="
python3 scripts/patch_settings_spa.py

echo "=== farm-ui build ==="
cd farm-ui
if [[ ! -d node_modules ]]; then npm install; fi
npm run build
cd "$ROOT"

echo "=== settings.js httpStatic /farm/ui ==="
bash scripts/pi-nodered-apply-settings-farm.sh

echo "=== merge + Node-RED flows ==="
python3 scripts/merge_nodered_deploy.py
bash scripts/pi-nodered-apply-merged.sh nodered/merged-deploy.json

echo "=== nginx (선택) ==="
if [[ -x scripts/pi-nginx-apply-cronusfarm.sh ]]; then
  bash scripts/pi-nginx-apply-cronusfarm.sh || true
fi

echo "OK: 설정 탭 클릭 → ${SPA_ENTRY:-/farm/ui/#/beds} · 브라우저에서 확인"
