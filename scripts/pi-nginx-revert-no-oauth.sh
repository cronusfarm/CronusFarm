#!/usr/bin/env bash
# HTTP 전환·Google OAuth 실험 되돌리기 — farm/ui·sqlite 로그인 없이, HTTPS→HTTP 강제 안 함
set -euo pipefail
ROOT="${HOME}/CronusFarm"
cd "$ROOT"

echo "=== nginx (저장소 conf, OAuth 비활성) ==="
sudo cp deploy/nginx/cronusfarm-nodered.conf /etc/nginx/sites-available/cronusfarm-nodered.conf
sudo ln -sf /etc/nginx/sites-available/cronusfarm-nodered.conf /etc/nginx/sites-enabled/cronusfarm-nodered.conf
# oauth2-full 이 다시 덮어쓰지 않도록 빈 include 만 사용
sudo cp deploy/nginx/cronusfarm-oauth2.conf /etc/nginx/cronusfarm-oauth2.conf
if [[ -f /etc/nginx/cronusfarm-oauth2.conf ]] && grep -q 'proxy_pass.*4180' /etc/nginx/cronusfarm-oauth2.conf 2>/dev/null; then
  echo '# OAuth 비활성' | sudo tee /etc/nginx/cronusfarm-oauth2.conf >/dev/null
fi

if [[ -f scripts/pi-nginx-strip-all-oauth-auth.py ]]; then
  sudo python3 scripts/pi-nginx-strip-all-oauth-auth.py
fi

# pi-nginx-https-to-http.sh 는 실행하지 않음

echo "=== oauth2-proxy 완전 중지 ==="
sudo touch /etc/cronusfarm/oauth2-disabled
sudo systemctl stop cronusfarm-oauth2-proxy 2>/dev/null || true
sudo systemctl disable cronusfarm-oauth2-proxy 2>/dev/null || true
sudo systemctl mask cronusfarm-oauth2-proxy 2>/dev/null || true

sudo nginx -t
sudo systemctl reload nginx

echo "=== 점검 ==="
curl -sS -m 5 -o /dev/null -w 'farm/ui:%{http_code}\n' -H 'Host: cronusfarm.duckdns.org' http://127.0.0.1/farm/ui/ || true
curl -sS -m 5 -o /dev/null -w 'ui:%{http_code}\n' -H 'Host: cronusfarm.duckdns.org' http://127.0.0.1/ui/ || true
echo "OK — http://cronusfarm.duckdns.org/ui/ · http://cronusfarm.duckdns.org/farm/ui/#/"
echo "     (Google OAuth 는 DuckDNS 공개 URL 에서 사용 안 함)"
