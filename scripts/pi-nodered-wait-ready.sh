#!/bin/bash
# Node-RED(기본 1882)가 nginx /ui 프록시에 응답할 때까지 대기
set -eu
PORT="${CRONUSFARM_NODERED_PORT:-1882}"
MAX="${1:-90}"
for i in $(seq 1 "$MAX"); do
  if timeout 1 bash -c "true </dev/tcp/127.0.0.1/${PORT}" 2>/dev/null; then
    # socket.io 루트는 400이어도 프로세스는 떠 있음
    echo "OK: Node-RED port ${PORT} ready (${i}s)"
    exit 0
  fi
  sleep 1
done
echo "WARN: Node-RED port ${PORT} not ready after ${MAX}s" >&2
exit 1
