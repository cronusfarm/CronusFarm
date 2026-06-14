#!/usr/bin/env bash
# oauth2 CSRF 수정: sign_in nginx 우회 제거, oauth2.conf 갱신, proxy 재시작
set -euo pipefail
CRONUS_ROOT="${CRONUS_ROOT:-$HOME/CronusFarm}"
OAUTH="/etc/nginx/cronusfarm-oauth2.conf"
FULL="$CRONUS_ROOT/deploy/nginx/cronusfarm-oauth2-full.conf"

sudo cp "$FULL" "$OAUTH"
# 구버전 sign_in 리다이렉트(location =) 제거 — include 파일에만 있던 경우
sudo sed -i '/^location = \/oauth2\/sign_in/,/^}$/d' "$OAUTH" 2>/dev/null || true

if grep -q 'return 302 /oauth2/sign_in' /etc/nginx/sites-enabled/cronusfarm-nodered.conf 2>/dev/null; then
  sudo sed -i 's|/oauth2/sign_in?rd=|/oauth2/start?rd=|g' /etc/nginx/sites-enabled/cronusfarm-nodered.conf
fi

bash "$CRONUS_ROOT/scripts/pi-install-oauth2-proxy-google.sh" 2>/dev/null || true
sudo systemctl restart cronusfarm-oauth2-proxy
sudo nginx -t
sudo systemctl reload nginx
echo "OK oauth2 CSRF fix — 브라우저 쿠키 삭제 후 https://cronusfarm.duckdns.org/farm/ui/ 재시도"
