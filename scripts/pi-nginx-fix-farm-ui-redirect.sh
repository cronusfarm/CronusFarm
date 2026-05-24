#!/usr/bin/env bash
set -euo pipefail
SITE="/etc/nginx/sites-enabled/cronusfarm-nodered.conf"
sudo sed -i '/location = \/farm\/ui {/{n;s/return 301 \/ui\;/return 301 \/farm\/ui\;/;}' "$SITE"
sudo nginx -t
sudo systemctl reload nginx
echo "OK:"
grep -A1 'location = /farm/ui {' "$SITE" | head -4
