#!/usr/bin/env bash
# (구) tailscale serve 443 은 duckdns nginx 443 과 충돌 → pi-nginx-enable-tailscale-ssl.sh 로 대체
set -euo pipefail
CRONUS_ROOT="${CRONUS_ROOT:-$HOME/CronusFarm}"
exec bash "$CRONUS_ROOT/scripts/pi-nginx-enable-tailscale-ssl.sh"
