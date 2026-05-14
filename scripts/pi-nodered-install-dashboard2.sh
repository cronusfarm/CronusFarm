#!/bin/bash
# Pi에서 실행: Dashboard 2(FlowFuse) 패키지 설치 — 플로우의 ui-base(/nrdb2)가 동작하려면 필수
# node-red-dashboard(v1)만 있으면 /ui 만 열리고 /nrdb2 는 404·빈 화면이 될 수 있음
set -eu

USERDIR="${HOME}/.node-red"
if [[ ! -d "$USERDIR" ]]; then
  echo "missing userDir: $USERDIR" >&2
  exit 1
fi

cd "$USERDIR"
if [[ -d node_modules/@flowfuse/node-red-dashboard ]]; then
  echo "OK: @flowfuse/node-red-dashboard already installed"
  exit 0
fi

echo "Installing @flowfuse/node-red-dashboard (Dashboard 2, /nrdb2)"
npm install @flowfuse/node-red-dashboard@1

if command -v systemctl >/dev/null 2>&1; then
  if systemctl is-active --quiet nodered.service 2>/dev/null; then
    sudo systemctl restart nodered.service || true
    echo "OK: nodered.service restarted"
  else
    echo "WARN: nodered.service is not active — restart manually"
  fi
fi
