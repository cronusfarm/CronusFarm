#!/bin/bash
# Pi: CronusFarm nginx 사이트 설정 반영(502 대응: body 크기·프록시 타임아웃 등은 저장소 conf에 포함)
# 사용: bash ~/CronusFarm/scripts/pi-nginx-apply-cronusfarm.sh [원본경로]
set -eu
# 비대화형 SSH·cron 등에서 PATH에 /usr/sbin 이 없으면 command -v nginx 가 실패하는 경우가 있음
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"
SRC="${1:-${HOME}/CronusFarm/deploy/nginx/cronusfarm-nodered.conf}"
if [[ ! -f "$SRC" ]]; then
  echo "missing conf file: $SRC" >&2
  exit 0
fi
if [[ ! -x /usr/sbin/nginx ]] && ! command -v nginx >/dev/null 2>&1; then
  echo "nginx not installed — skip (install: sudo apt install -y nginx)" >&2
  exit 0
fi
if ! sudo -n true 2>/dev/null; then
  echo "WARN: sudo -n not allowed — on Pi run: sudo cp '$SRC' /etc/nginx/sites-available/cronusfarm-nodered.conf && sudo ln -sf /etc/nginx/sites-available/cronusfarm-nodered.conf /etc/nginx/sites-enabled/ && sudo nginx -t && sudo systemctl reload nginx" >&2
  exit 0
fi
sudo cp "$SRC" /etc/nginx/sites-available/cronusfarm-nodered.conf
AUTH_SRC="${HOME}/CronusFarm/deploy/nginx/cronusfarm-auth.conf"
if [[ -f "$AUTH_SRC" ]]; then
  sudo cp "$AUTH_SRC" /etc/nginx/cronusfarm-auth.conf
elif [[ ! -f /etc/nginx/cronusfarm-auth.conf ]]; then
  sudo touch /etc/nginx/cronusfarm-auth.conf
fi
OAUTH_SRC="${HOME}/CronusFarm/deploy/nginx/cronusfarm-oauth2.conf"
if [[ -f "$OAUTH_SRC" ]]; then
  sudo cp "$OAUTH_SRC" /etc/nginx/cronusfarm-oauth2.conf
elif [[ ! -f /etc/nginx/cronusfarm-oauth2.conf ]]; then
  sudo touch /etc/nginx/cronusfarm-oauth2.conf
fi
sudo ln -sf /etc/nginx/sites-available/cronusfarm-nodered.conf /etc/nginx/sites-enabled/cronusfarm-nodered.conf
# Debian/Ubuntu 기본 default 사이트가 listen 80 default_server 이면 CronusFarm 적용 후에도 "Welcome to nginx!" 만 보임
if [[ -e /etc/nginx/sites-enabled/default ]] || [[ -L /etc/nginx/sites-enabled/default ]]; then
  sudo rm -f /etc/nginx/sites-enabled/default
  echo "removed sites-enabled/default (기본 환영 페이지 비활성화)"
fi
sudo nginx -t
sudo systemctl reload nginx
# Let's Encrypt 인증서가 있으면 443 ssl 블록 재주입(저장소 conf 덮어쓰기 시 443 소실 방지)
if command -v certbot >/dev/null 2>&1 \
  && [[ -d /etc/letsencrypt/live/cronusfarm.duckdns.org ]]; then
  sudo certbot install --cert-name cronusfarm.duckdns.org --nginx \
    --redirect --non-interactive 2>/dev/null \
    || echo "WARN: certbot install 실패 — bash ~/CronusFarm/scripts/pi-setup-duckdns-https.sh"
fi
echo "OK: nginx cronusfarm-nodered.conf applied and reloaded"
