#!/usr/bin/env bash
# oauth2-proxy 동작 중일 때 공개 호스트(cronusfarm.duckdns.org)만 auth_request 적용
set -euo pipefail
CRONUS_ROOT="${CRONUS_ROOT:-$HOME/CronusFarm}"
SITE="/etc/nginx/sites-enabled/cronusfarm-nodered.conf"
OAUTH_MAIN="/etc/nginx/cronusfarm-oauth2.conf"
MARK="CRONUSFARM_OAUTH2_AUTH"

_oauth_code="$(curl -sS -m 2 -o /dev/null -w '%{http_code}' http://127.0.0.1:4180/oauth2/auth 2>/dev/null || echo 000)"
if [[ "$_oauth_code" == "000" ]]; then
  echo "WARN: oauth2-proxy(4180) 응답 없음 — auth_request 적용 생략"
  exit 0
fi

sudo cp "$CRONUS_ROOT/deploy/nginx/cronusfarm-oauth2.conf" "$OAUTH_MAIN" 2>/dev/null || true
if [[ -f "$CRONUS_ROOT/deploy/nginx/cronusfarm-oauth2-full.conf" ]]; then
  sudo cp "$CRONUS_ROOT/deploy/nginx/cronusfarm-oauth2-full.conf" "$OAUTH_MAIN"
fi

bash "$CRONUS_ROOT/scripts/pi-nginx-patch-oauth-host-only.sh"

# 이전 실패 시 server 블록 밖에 붙은 조각 제거
sudo sed -i '/^# '"$MARK"'$/,/^}$/d' "$SITE" 2>/dev/null || true

if ! grep -q '@oauth2_sign_in' "$SITE" 2>/dev/null; then
  sudo sed -i '/include \/etc\/nginx\/cronusfarm-oauth2.conf;/a\
\
  # '"$MARK"'\
  location @oauth2_sign_in {\
    return 302 /oauth2/start?rd=$scheme://$host$request_uri;\
  }' "$SITE"
  echo "added @oauth2_sign_in inside server block"
fi

if grep -q 'auth_request \$cf_oauth_auth_uri' "$SITE" 2>/dev/null; then
  echo "skip: auth_request already present"
  sudo nginx -t && sudo systemctl reload nginx
  exit 0
fi

sudo python3 "$CRONUS_ROOT/scripts/pi-nginx-apply-oauth-auth-locations.py"

sudo nginx -t
sudo systemctl reload nginx
echo "OK OAuth auth_request (duckdns host only) on $SITE"
