#!/usr/bin/env bash
# DuckDNS HTTPS(443) — certbot 인증서 + nginx 프록시(→ :80 기존 cronusfarm-nodered)
set -euo pipefail
ROOT="${CRONUSFARM_ROOT:-$HOME/CronusFarm}"
SRC="$ROOT/deploy/nginx/cronusfarm-duckdns-443.conf"
DST="/etc/nginx/conf.d/cronusfarm-duckdns-443.conf"
CERT="/etc/letsencrypt/live/cronusfarm.duckdns.org/fullchain.pem"

if [[ ! -f "$SRC" ]]; then
  echo "없음: $SRC" >&2
  exit 1
fi
if [[ ! -f "$CERT" ]]; then
  echo "certbot 인증서 없음: $CERT — certbot certonly --nginx -d cronusfarm.duckdns.org" >&2
  exit 1
fi

sudo cp -f "$SRC" "$DST"
sudo nginx -t
sudo systemctl reload nginx
echo "OK: https://cronusfarm.duckdns.org/ (DuckDNS cert on 443)"
