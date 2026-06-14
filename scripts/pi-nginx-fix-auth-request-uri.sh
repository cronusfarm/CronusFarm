#!/usr/bin/env bash
# 고정 auth_request /oauth2/auth 는 Tailscale HTTPS까지 Google 로그인 유도 → 느림.
# DuckDNS(443)만 $cf_oauth_auth_uri (빈 값이면 auth 생략).
set -euo pipefail
CRONUS_ROOT="${CRONUS_ROOT:-$HOME/CronusFarm}"
bash "$CRONUS_ROOT/scripts/pi-nginx-patch-oauth-host-only.sh"
