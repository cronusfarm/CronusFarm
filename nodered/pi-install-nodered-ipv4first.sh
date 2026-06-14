#!/usr/bin/env bash
# Pi: Node-RED가 Telegram 등 외부 HTTPS를 IPv4로 먼저 쓰도록 systemd drop-in 적용
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/deploy/systemd/nodered.service.d/30-cronusfarm-ipv4first.conf"
DST_DIR="/etc/systemd/system/nodered.service.d"
sudo mkdir -p "$DST_DIR"
sudo cp "$SRC" "$DST_DIR/30-cronusfarm-ipv4first.conf"
sudo systemctl daemon-reload
sudo systemctl restart nodered
echo "OK: NODE_OPTIONS=--dns-result-order=ipv4first 적용 + nodered 재시작"
