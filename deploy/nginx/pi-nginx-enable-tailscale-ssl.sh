#!/usr/bin/env bash
# Tailscale MagicDNS HTTPS — nginx 443 + tailscale cert (tailscale serve 와 충돌하므로 serve 끔)
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"
TS_HOST="${CRONUSFARM_TS_HOST:-ida.mango-larch.ts.net}"
CRONUS_ROOT="${CRONUS_ROOT:-$HOME/CronusFarm}"
SSL_DIR="/etc/nginx/ssl/tailscale"
CONF_DST="/etc/nginx/conf.d/cronusfarm-tailscale-443.conf"
CONF_SRC="$CRONUS_ROOT/deploy/nginx/cronusfarm-tailscale-443.conf"

sudo tailscale serve reset 2>/dev/null || true
sudo mkdir -p "$SSL_DIR"
sudo tailscale cert "$TS_HOST"
sudo cp -f "${TS_HOST}.crt" "$SSL_DIR/fullchain.pem"
sudo cp -f "${TS_HOST}.key" "$SSL_DIR/privkey.pem"
sudo chmod 644 "$SSL_DIR/fullchain.pem"
sudo chmod 600 "$SSL_DIR/privkey.pem"
if [[ -f "$CONF_SRC" ]]; then
  sudo cp "$CONF_SRC" "$CONF_DST"
else
  echo "WARN: $CONF_SRC 없음" >&2
fi
sudo nginx -t
sudo systemctl reload nginx
echo "OK: https://${TS_HOST}/ → nginx:443 (tailscale cert)"
