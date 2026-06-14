#!/usr/bin/env bash
# Pi: oauth2-proxy + Google OAuth + nginx auth_request
# 사용 전 Google Cloud Console 에서 OAuth 클라이언트 생성 후 env 편집
set -euo pipefail

CRONUS_ROOT="${CRONUS_ROOT:-$HOME/CronusFarm}"
ENV_FILE="/etc/cronusfarm/oauth2-proxy.env"
CFG_FILE="/etc/cronusfarm/oauth2-proxy.cfg"
NGINX_OAUTH="$CRONUS_ROOT/deploy/nginx/cronusfarm-oauth2.conf"
NGINX_SITE="/etc/nginx/cronusfarm-oauth2.conf"
UNIT_SRC="$CRONUS_ROOT/deploy/systemd/cronusfarm-oauth2-proxy.service"

echo "=== oauth2-proxy 설치 ==="
if ! command -v oauth2-proxy >/dev/null 2>&1; then
  VER="${OAUTH2_PROXY_VERSION:-7.6.0}"
  ARCH="$(uname -m)"
  case "$ARCH" in
    aarch64|arm64) A=arm64 ;;
    x86_64|amd64) A=amd64 ;;
    *) echo "unsupported arch: $ARCH"; exit 1 ;;
  esac
  URL="https://github.com/oauth2-proxy/oauth2-proxy/releases/download/v${VER}/oauth2-proxy-v${VER}.linux-${A}.tar.gz"
  TMP="$(mktemp -d)"
  curl -fsSL "$URL" | tar -xz -C "$TMP"
  sudo install -m 0755 "$TMP"/oauth2-proxy-*/oauth2-proxy /usr/local/bin/oauth2-proxy
  rm -rf "$TMP"
fi

sudo mkdir -p /etc/cronusfarm
ENV_EX="${CRONUS_ROOT}/deploy/env/oauth2-proxy.env.example"
if [[ ! -f "$ENV_FILE" && -f "$ENV_EX" ]]; then
  sudo cp "$ENV_EX" "$ENV_FILE"
  echo "생성: $ENV_FILE (example 복사) — CLIENT_ID/SECRET 편집"
fi

if [[ ! -f "$ENV_FILE" ]]; then
  sudo tee "$ENV_FILE" >/dev/null <<'EOF'
# Google OAuth — Console에서 발급 후 채우기
OAUTH2_PROXY_CLIENT_ID=
OAUTH2_PROXY_CLIENT_SECRET=
# Tailscale HTTPS 또는 공개 URL (슬래시 없음)
OAUTH2_PROXY_REDIRECT_URL=https://cronusfarm.duckdns.org/oauth2/callback
# 허용 이메일 도메인 (* = 로그인한 Google 계정 모두)
OAUTH2_PROXY_EMAIL_DOMAINS=*
EOF
  echo "생성: $ENV_FILE — CLIENT_ID/SECRET 을 편집하세요."
fi

# env 로드 (640 root:dooly 또는 sudo)
_oauth_env_get() {
  local key="$1"
  if [[ -r "$ENV_FILE" ]]; then
    grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | head -1
  else
    sudo grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | head -1
  fi
}
_oauth_strip() {
  printf '%s' "$1" | tr -d '\r\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}
OAUTH2_PROXY_CLIENT_ID="$(_oauth_strip "$(_oauth_env_get OAUTH2_PROXY_CLIENT_ID)")"
OAUTH2_PROXY_CLIENT_SECRET="$(_oauth_strip "$(_oauth_env_get OAUTH2_PROXY_CLIENT_SECRET)")"
REDIRECT="$(_oauth_strip "$(_oauth_env_get OAUTH2_PROXY_REDIRECT_URL)")"
REDIRECT="${REDIRECT:-https://cronusfarm.duckdns.org/oauth2/callback}"
OAUTH2_PROXY_EMAIL_DOMAINS="$(_oauth_env_get OAUTH2_PROXY_EMAIL_DOMAINS)"
OAUTH2_PROXY_EMAIL_DOMAINS="${OAUTH2_PROXY_EMAIL_DOMAINS:-*}"
COOKIE_FILE="/etc/cronusfarm/oauth2-cookie-secret"
# 32바이트 ASCII (oauth2-proxy cookie-secret 길이 요구)
python3 -c 'import secrets,string; a=string.ascii_letters+string.digits; print("".join(secrets.choice(a) for _ in range(32)), end="")' | sudo tee "$COOKIE_FILE" >/dev/null
sudo chmod 600 "$COOKIE_FILE"

sudo tee "$CFG_FILE" >/dev/null <<EOF
provider = "google"
client_id = "${OAUTH2_PROXY_CLIENT_ID:-}"
client_secret = "${OAUTH2_PROXY_CLIENT_SECRET:-}"
redirect_url = "${REDIRECT}"
email_domains = [ "${OAUTH2_PROXY_EMAIL_DOMAINS:-*}" ]
upstreams = [ "static://200" ]
http_address = "127.0.0.1:4180"
reverse_proxy = true
cookie_secure = true
cookie_httponly = true
cookie_samesite = "lax"
set_xauthrequest = true
pass_access_token = false
pass_authorization_header = false
skip_provider_button = false
EOF

sudo cp "$UNIT_SRC" /etc/systemd/system/cronusfarm-oauth2-proxy.service
sudo systemctl daemon-reload

FULL="$CRONUS_ROOT/deploy/nginx/cronusfarm-oauth2-full.conf"
if [[ -f "$FULL" ]]; then
  sudo cp "$FULL" "$NGINX_SITE"
elif [[ -f "$NGINX_OAUTH" ]]; then
  sudo cp "$NGINX_OAUTH" "$NGINX_SITE"
fi

# nginx 메인 사이트에 auth_request 블록 삽입 (이미 있으면 스킵)
MAIN="/etc/nginx/sites-enabled/cronusfarm-nodered.conf"
if [[ -f "$MAIN" ]] && ! grep -q 'cronusfarm-oauth2.conf' "$MAIN"; then
  sudo sed -i '/cronusfarm-auth.conf/a \  include /etc/nginx/cronusfarm-oauth2.conf;' "$MAIN" 2>/dev/null || true
fi

if [[ -n "${OAUTH2_PROXY_CLIENT_ID:-}" && -n "${OAUTH2_PROXY_CLIENT_SECRET:-}" ]]; then
  sudo systemctl enable --now cronusfarm-oauth2-proxy.service
  echo "oauth2-proxy 시작됨"
else
  echo "WARN: CLIENT_ID/SECRET 비어 있음 — $ENV_FILE 편집 후: sudo systemctl restart cronusfarm-oauth2-proxy"
fi

echo "=== nginx OAuth (DuckDNS 호스트만) ==="
if [[ -x "$CRONUS_ROOT/scripts/pi-nginx-patch-oauth-host-only.sh" ]]; then
  bash "$CRONUS_ROOT/scripts/pi-nginx-patch-oauth-host-only.sh" || true
fi
if [[ -x "$CRONUS_ROOT/scripts/pi-nginx-enable-oauth2-auth.sh" ]]; then
  bash "$CRONUS_ROOT/scripts/pi-nginx-enable-oauth2-auth.sh"
fi

sudo nginx -t && sudo systemctl reload nginx
echo "OK oauth2-proxy. Redirect URI: ${REDIRECT}"
