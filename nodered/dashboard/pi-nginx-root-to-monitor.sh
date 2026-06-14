#!/usr/bin/env bash
# 루트(/) → /ui/ (모니터). farm-ui 설정은 /farm/ui/
set -euo pipefail
SITE="/etc/nginx/sites-enabled/cronusfarm-nodered.conf"
sudo sed -i 's|location = / { return 301 /farm/ui/; }|location = / { return 301 /ui/; }|g' "$SITE"
sudo sed -i 's|return 301 /farm/ui/;|return 301 /ui/;|g' "$SITE" 2>/dev/null || true
sudo nginx -t
sudo systemctl reload nginx
echo "OK root -> /ui/"
