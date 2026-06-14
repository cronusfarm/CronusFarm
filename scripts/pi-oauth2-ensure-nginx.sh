#!/usr/bin/env bash
# oauth2-proxy 가 떠 있는데 nginx /oauth2/ location 이 비어 있으면 복구
set -euo pipefail
CRONUS_ROOT="${CRONUS_ROOT:-$HOME/CronusFarm}"
OAUTH_MAIN="/etc/nginx/cronusfarm-oauth2.conf"
FULL="$CRONUS_ROOT/deploy/nginx/cronusfarm-oauth2-full.conf"

if [[ -f /etc/cronusfarm/oauth2-disabled ]]; then
  exit 0
fi
if ! systemctl is-active --quiet cronusfarm-oauth2-proxy 2>/dev/null; then
  exit 0
fi
if [[ ! -f "$FULL" ]]; then
  exit 0
fi
if grep -q 'location /oauth2/' "$OAUTH_MAIN" 2>/dev/null; then
  exit 0
fi
echo "WARN: $OAUTH_MAIN 에 /oauth2/ 없음 — full 설정 적용"
sudo cp "$FULL" "$OAUTH_MAIN"
sudo nginx -t
sudo systemctl reload nginx
echo "OK pi-oauth2-ensure-nginx"
