#!/usr/bin/env bash
# server 블록 밖에 붙은 @oauth2_sign_in 제거 후 첫 server 블록 안으로 삽입
set -euo pipefail
SITE="/etc/nginx/sites-enabled/cronusfarm-nodered.conf"
MARK="CRONUSFARM_OAUTH2_AUTH"

sudo sed -i '/^# '"$MARK"'$/,/^}$/d' "$SITE" 2>/dev/null || true
sudo sed -i '/^location @oauth2_sign_in/,/^}$/d' "$SITE" 2>/dev/null || true

if ! grep -q '@oauth2_sign_in' "$SITE"; then
  sudo awk '
    /include \/etc\/nginx\/cronusfarm-oauth2.conf;/ && !done {
      print
      print ""
      print "  # '"$MARK"'"
      print "  location @oauth2_sign_in {"
      print "    return 302 /oauth2/sign_in?rd=$scheme://$host$request_uri;"
      print "  }"
      done=1
      next
    }
    { print }
  ' "$SITE" | sudo tee "${SITE}.tmp" >/dev/null
  sudo mv "${SITE}.tmp" "$SITE"
  echo "inserted @oauth2_sign_in"
fi

sudo nginx -t
