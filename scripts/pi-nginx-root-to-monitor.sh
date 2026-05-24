#!/usr/bin/env bash
# 루트(/) → /ui/ (모니터). farm-ui 설정은 /farm/ui/
set -euo pipefail
SITE="/etc/nginx/sites-enabled/cronusfarm-nodered.conf"
sudo sed -i 's|location = / { return 301 /farm/ui/; }|location = / { return 301 /ui/; }|g' "$SITE"
# /farm/ui/ 설정 SPA 리다이렉트는 건드리지 않음 (광역 sed 금지)
if grep -q 'location = /farm/ui {' "$SITE" && grep -A1 'location = /farm/ui {' "$SITE" | grep -q 'return 301 /ui/;'; then
  sudo sed -i '/location = \/farm\/ui {/,/}/ s|return 301 /ui/;|return 301 /farm/ui/;|' "$SITE"
fi
sudo nginx -t
sudo systemctl reload nginx
echo "OK root -> /ui/"
