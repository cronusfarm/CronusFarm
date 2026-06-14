#!/usr/bin/env bash
# /farm/ui → /farm/ui/ (설정 SPA). 루트(/)만 /ui/ 로 보냄.
set -euo pipefail
SITE="/etc/nginx/sites-enabled/cronusfarm-nodered.conf"
sudo perl -i -pe 's/^(\s*location = \/farm\/ui \{\s*)$/location = \/farm\/ui {/; if ($in_farm_ui) { s/return 301 \/ui\;/return 301 \/farm\/ui\;/; $in_farm_ui=0 } $in_farm_ui=1 if /location = \/farm\/ui \{/ && !/\/farm\/ui\//;' "$SITE" 2>/dev/null || true
# perl 실패 시: farm/ui 블록 다음 줄만 치환
while grep -q 'location = /farm/ui {' "$SITE" && grep -A1 'location = /farm/ui {' "$SITE" | grep -q 'return 301 /ui/;'; do
  sudo sed -i '/location = \/farm\/ui {/{n;s/return 301 \/ui\;/return 301 \/farm\/ui\;/;}' "$SITE"
done
sudo nginx -t
sudo systemctl reload nginx
grep -A1 'location = /farm/ui {' "$SITE" | head -4
echo "OK farm/ui redirect"
