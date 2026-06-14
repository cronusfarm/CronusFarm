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

sudo sed -i 's/auth_request \/oauth2\/auth;/auth_request $cf_oauth_auth_uri;/g' "$SITE"
sudo nginx -t
sudo systemctl reload nginx
echo "OK OAuth host map — duckdns only"
