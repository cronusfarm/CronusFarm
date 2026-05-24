#!/usr/bin/env bash
# CronusFarm nginx HTTP Basic Auth — /ui/ · /farm/ui/ 로그인
# Google/Kakao OAuth 대신 Pi·Tailscale 환경에서 가장 단순한 보호(브라우저 ID/비밀번호)
#
# 사용 (Pi):
#   bash ~/CronusFarm/scripts/pi-nginx-set-basic-auth.sh dooly
#   (비밀번호 입력 프롬프트)
#
# 해제:
#   sudo rm -f /etc/nginx/cronusfarm-auth.conf /etc/nginx/cronusfarm-htpasswd
#   sudo systemctl reload nginx
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"

USER_NAME="${1:-}"
if [[ -z "$USER_NAME" ]]; then
  echo "usage: $0 <username>" >&2
  exit 1
fi

if ! command -v htpasswd >/dev/null 2>&1; then
  echo "install: sudo apt install -y apache2-utils" >&2
  exit 1
fi

HTPASS="/etc/nginx/cronusfarm-htpasswd"
AUTH_CONF="/etc/nginx/cronusfarm-auth.conf"

sudo htpasswd -c "$HTPASS" "$USER_NAME"
sudo tee "$AUTH_CONF" >/dev/null <<'EOF'
auth_basic "CronusFarm";
auth_basic_user_file /etc/nginx/cronusfarm-htpasswd;
EOF

ROOT="${HOME}/CronusFarm"
if [[ -f "$ROOT/deploy/nginx/cronusfarm-nodered.conf" ]]; then
  sudo cp "$ROOT/deploy/nginx/cronusfarm-nodered.conf" /etc/nginx/sites-available/cronusfarm-nodered.conf
  sudo ln -sf /etc/nginx/sites-available/cronusfarm-nodered.conf /etc/nginx/sites-enabled/cronusfarm-nodered.conf
fi
sudo nginx -t
sudo systemctl reload nginx
echo "OK: Basic Auth enabled for /ui/ and /farm/ui/ (user=$USER_NAME)"
