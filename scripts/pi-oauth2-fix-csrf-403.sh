#!/usr/bin/env bash
# oauth2 콜백 403 (CSRF cookie / redirect whitelist) — nginx proto + oauth2-proxy.cfg
set -euo pipefail
ROOT="${HOME}/CronusFarm"
cd "$ROOT"

echo "=== nginx maps + oauth2 include ==="
sudo cp deploy/nginx/cronusfarm-nodered.conf /etc/nginx/sites-available/cronusfarm-nodered.conf
sudo cp deploy/nginx/cronusfarm-oauth2-full.conf /etc/nginx/cronusfarm-oauth2.conf

if [[ -f scripts/pi-nginx-apply-oauth-auth-locations.py ]]; then
  sudo python3 scripts/pi-nginx-apply-oauth-auth-locations.py
fi

echo "=== oauth2-proxy whitelist_domains ==="
CFG="/etc/cronusfarm/oauth2-proxy.cfg"
if [[ -f "$CFG" ]] && ! grep -q 'whitelist_domains' "$CFG"; then
  sudo sed -i '/^email_domains/a whitelist_domains = [ "cronusfarm.duckdns.org", ".duckdns.org", "ida.mango-larch.ts.net" ]' "$CFG"
fi

sudo nginx -t
sudo systemctl reload nginx
sudo systemctl restart cronusfarm-oauth2-proxy
sleep 2
curl -sS -m 3 -o /dev/null -w 'oauth2/auth:%{http_code}\n' http://127.0.0.1:4180/oauth2/auth || true
echo "OK pi-oauth2-fix-csrf-403.sh"
