#!/usr/bin/env bash
# cronusfarm.duckdns.org — Let's Encrypt + nginx HTTPS(443)
# 전제: 라우터 80·443 → Pi, DuckDNS A 레코드 = 현재 공인 IP
# DuckDNS + LE: CAA/A 조회 타임아웃이 간헐적 → 이 스크립트는 사전 점검 후 certbot 재시도
set -euo pipefail

DOMAIN="${CRONUSFARM_HTTPS_DOMAIN:-cronusfarm.duckdns.org}"
EMAIL="${CERTBOT_EMAIL:-}"
CRONUS_ROOT="${CRONUS_ROOT:-$HOME/CronusFarm}"
RETRIES="${CERTBOT_RETRIES:-6}"
RETRY_SLEEP="${CERTBOT_RETRY_SLEEP:-90}"
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"

echo "=== HTTPS setup: $DOMAIN ==="

if ! command -v nginx >/dev/null 2>&1; then
  echo "nginx 없음 — sudo apt install -y nginx" >&2
  exit 1
fi

if [[ -f "$CRONUS_ROOT/scripts/pi-duckdns-update-ip.sh" ]]; then
  bash "$CRONUS_ROOT/scripts/pi-duckdns-update-ip.sh" || true
fi

if [[ -f "$CRONUS_ROOT/scripts/pi-nginx-apply-cronusfarm.sh" ]]; then
  bash "$CRONUS_ROOT/scripts/pi-nginx-apply-cronusfarm.sh" \
    "$CRONUS_ROOT/deploy/nginx/cronusfarm-nodered.conf"
fi

sudo touch /etc/nginx/cronusfarm-oauth2.conf
sudo mkdir -p /etc/cronusfarm

if ! command -v certbot >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y certbot python3-certbot-nginx
fi

echo "=== 사전 점검 (DNS·공인 IP) ==="
PUBLIC_IP=""
if command -v curl >/dev/null 2>&1; then
  PUBLIC_IP="$(curl -4 -sS --max-time 10 https://api.ipify.org 2>/dev/null || true)"
fi
RESOLVED_IP=""
if command -v getent >/dev/null 2>&1; then
  RESOLVED_IP="$(getent ahostsv4 "$DOMAIN" 2>/dev/null | awk '{print $1; exit}')"
fi
echo "공인 IP(IPv4): ${PUBLIC_IP:-?}"
echo "DNS A ($DOMAIN): ${RESOLVED_IP:-?}"
if [[ -n "$PUBLIC_IP" && -n "$RESOLVED_IP" && "$PUBLIC_IP" != "$RESOLVED_IP" ]]; then
  echo "WARN: DuckDNS A 레코드가 Pi 공인 IP와 다릅니다." >&2
  echo "  → https://www.duckdns.org 에서 도메인 IP 갱신 또는:" >&2
  echo "  → /etc/cronusfarm/duckdns.env 설정 후 pi-duckdns-update-ip.sh" >&2
fi
if [[ -z "$RESOLVED_IP" ]]; then
  echo "WARN: 이 Pi에서 $DOMAIN DNS 조회 실패 — DuckDNS·인터넷 확인" >&2
fi

CERT_ARGS=(--nginx -d "$DOMAIN" --non-interactive --agree-tos --redirect)
if [[ -n "$EMAIL" ]]; then
  CERT_ARGS+=(--email "$EMAIL")
else
  CERT_ARGS+=(--register-unsafely-without-email)
fi

echo "=== certbot (nginx, 최대 ${RETRIES}회, ${RETRY_SLEEP}초 간격) ==="
echo "참고: DuckDNS는 Let's Encrypt 'secondary validation'에서 CAA/A 타임아웃이 잦습니다. 실패 시 잠시 후 재실행하세요."
ok=0
for ((i = 1; i <= RETRIES; i++)); do
  echo "--- 시도 $i / $RETRIES ---"
  if sudo certbot "${CERT_ARGS[@]}"; then
    ok=1
    break
  fi
  if [[ "$i" -lt "$RETRIES" ]]; then
    echo "certbot 실패 — ${RETRY_SLEEP}초 후 재시도 (DuckDNS DNS 일시 오류 가능)..."
    sleep "$RETRY_SLEEP"
  fi
done

if [[ "$ok" -ne 1 ]]; then
  echo "" >&2
  echo "인증서 발급 실패. 확인 사항:" >&2
  echo "  1) 라우터 포워딩: TCP 80·443 → Pi (HTTP-01에 80 필수)" >&2
  echo "  2) https://www.duckdns.org — cronusfarm IP = 공인 IP ${PUBLIC_IP:-?}" >&2
  echo "  3) 1~2시간 뒤 동일 스크립트 재실행 (DuckDNS DNS 타임아웃은 간헐적)" >&2
  echo "  4) letsdebug.net 에서 $DOMAIN 검사" >&2
  exit 1
fi

sudo nginx -t
sudo systemctl reload nginx

echo "=== 확인 ==="
curl -sI "https://$DOMAIN/" | head -5 || true
echo "OK: https://$DOMAIN/"
echo "Google Redirect URI: https://$DOMAIN/oauth2/callback"
