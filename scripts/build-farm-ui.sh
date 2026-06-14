#!/usr/bin/env bash
# CronusFarm 설정 SPA (farm-ui) 빌드 — Pi·Linux용 (Windows는 build-farm-ui.ps1)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FARM_UI="${ROOT}/farm-ui"

if [[ ! -d "${FARM_UI}" ]]; then
  echo "farm-ui 없음: ${FARM_UI}" >&2
  exit 1
fi

cd "${FARM_UI}"
if [[ ! -d node_modules ]]; then
  echo "=== farm-ui: npm install ==="
  npm install
fi
echo "=== farm-ui: npm run build ==="
npm run build
if [[ ! -f dist/index.html ]]; then
  echo "dist/index.html 없음 — base=/farm/ui/ 빌드 확인" >&2
  exit 1
fi
echo "[OK] farm-ui dist: ${FARM_UI}/dist/index.html"
