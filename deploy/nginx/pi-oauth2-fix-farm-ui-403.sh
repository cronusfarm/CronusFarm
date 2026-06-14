#!/usr/bin/env bash
# /farm/ui/ 403 Forbidden (oauth2 CSRF·redirect URL·cookie) 복구
set -euo pipefail
ROOT="${HOME}/CronusFarm}"
cd "$ROOT"

echo "=== nginx (DuckDNS OAuth proto=https) ==="
sudo cp deploy/nginx/cronusfarm-nodered.conf /etc/nginx/sites-available/cronusfarm-nodered.conf
sudo ln -sf /etc/nginx/sites-available/cronusfarm-nodered.conf /etc/nginx/sites-enabled/cronusfarm-nodered.conf
sudo cp deploy/nginx/cronusfarm-oauth2-full.conf /etc/nginx/cronusfarm-oauth2.conf

if [[ -f scripts/pi-nginx-apply-oauth-auth-locations.py ]]; then
  sudo python3 scripts/pi-nginx-apply-oauth-auth-locations.py
fi

echo "=== oauth2-proxy: HTTPS 콜백 (Google Console 과 일치) ==="
ENV="/etc/cronusfarm/oauth2-proxy.env"
CFG="/etc/cronusfarm/oauth2-proxy.cfg"
for f in "$ENV" "$CFG"; do
  [[ -f "$f" ]] || continue
  sudo sed -i 's|^OAUTH2_PROXY_REDIRECT_URL=http://|OAUTH2_PROXY_REDIRECT_URL=https://|' "$f" 2>/dev/null || true
  sudo sed -i 's|^redirect_url = http://|redirect_url = https://|' "$f" 2>/dev/null || true
done
if [[ -f "$CFG" ]]; then
  sudo sed -i 's/^cookie_secure = false/cookie_secure = true/' "$CFG" 2>/dev/null || true
  if ! grep -q 'whitelist_domains' "$CFG"; then
    sudo sed -i '/^email_domains/a whitelist_domains = [ "cronusfarm.duckdns.org", ".duckdns.org", "ida.mango-larch.ts.net" ]' "$CFG"
  fi
fi

# DuckDNS 443: OAuth 를 위해 프록시 유지(전부 http 리다이렉트 시 Google 콜백 깨짐)
SITE="/etc/nginx/sites-available/cronusfarm-nodered.conf"
if [[ -f "$SITE" ]] && grep -q 'listen 443' "$SITE"; then
  sudo python3 - "$SITE" <<'PY'
import re, sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
parts = re.split(r"(?=\nserver\s*\{)", text)
out = []
for block in parts:
    if "listen 443" in block and "cronusfarm.duckdns.org" in block:
        if "return 301 http://" in block and "ssl_certificate" in block:
            # certbot 443 블록을 프록시로 복원(간이 리다이렉트 제거)
            m = re.search(r"ssl_certificate\s+([^;]+);\s*\n\s*ssl_certificate_key\s+([^;]+);", block)
            if m:
                block = (
                    "server {\n"
                    "  listen 443 ssl;\n"
                    "  listen [::]:443 ssl;\n"
                    "  server_name cronusfarm.duckdns.org;\n\n"
                    f"  ssl_certificate     {m.group(1)};\n"
                    f"  ssl_certificate_key {m.group(2)};\n"
                    "  include /etc/letsencrypt/options-ssl-nginx.conf;\n\n"
                    "  client_max_body_size 20m;\n"
                    "  include /etc/nginx/cronusfarm-auth.conf;\n"
                    "  include /etc/nginx/cronusfarm-oauth2.conf;\n\n"
                    "  location / {\n"
                    "    proxy_pass http://127.0.0.1:80;\n"
                    "    proxy_http_version 1.1;\n"
                    "    proxy_set_header Host $host;\n"
                    "    proxy_set_header X-Real-IP $remote_addr;\n"
                    "    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n"
                    "    proxy_set_header X-Forwarded-Proto https;\n"
                    "    proxy_set_header Upgrade $http_upgrade;\n"
                    "    proxy_set_header Connection $connection_upgrade;\n"
                    "  }\n"
                    "}\n"
                )
                print("OK duckdns 443 → :80 proxy (X-Forwarded-Proto https)")
    out.append(block)
open(path, "w", encoding="utf-8").write("".join(out))
PY
fi

sudo nginx -t
sudo systemctl reload nginx
sudo systemctl restart cronusfarm-oauth2-proxy 2>/dev/null || true
sleep 2

echo "=== 점검 ==="
curl -sS -m 5 -o /dev/null -w 'farm/ui/:%{http_code}\n' -H 'Host: cronusfarm.duckdns.org' http://127.0.0.1/farm/ui/ || true
curl -sS -m 3 -o /dev/null -w 'oauth2/auth:%{http_code}\n' http://127.0.0.1:4180/oauth2/auth || true
echo "OK — 브라우저: https://cronusfarm.duckdns.org/oauth2/sign_out 후 재로그인"
echo "     farm-ui: https://cronusfarm.duckdns.org/farm/ui/#/"
