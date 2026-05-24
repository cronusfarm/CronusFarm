#!/usr/bin/env bash
# OAuth auth_request 를 cronusfarm.duckdns.org 호스트에만 적용 (Tailscale *.ts.net 제외)
set -euo pipefail
CRONUS_ROOT="${CRONUS_ROOT:-$HOME/CronusFarm}"
SITE="/etc/nginx/sites-enabled/cronusfarm-nodered.conf"
MAP_MARK="cf_oauth_auth_uri"

if ! grep -q "$MAP_MARK" "$SITE" 2>/dev/null; then
  sudo sed -i "/^map \$http_upgrade \$connection_upgrade {/,/^}/{
    /^}/a\\
\\
# Google OAuth: 공개 DuckDNS만 (Tailscale은 VPN 인증)\\
map \$host \$cf_oauth_auth_uri {\\
  default \"\";\\
  cronusfarm.duckdns.org /oauth2/auth;\\
}
  }" "$SITE"
  echo "added map \$cf_oauth_auth_uri"
fi

# auth_request $변수 는 이 nginx에서 미확장(500) → pi-nginx-443-tailscale-no-oauth.py 사용
if ! grep -q 'CRONUSFARM_443_TAILSCALE_DEV' "$SITE" 2>/dev/null; then
  echo "WARN: run pi-nginx-443-tailscale-no-oauth.py for Tailscale HTTPS"
fi
sudo nginx -t
sudo systemctl reload nginx
echo "OK OAuth host map — duckdns only"
