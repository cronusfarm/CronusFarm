#!/usr/bin/env bash
# Tailscale MagicDNS(https://*.ts.net) → 로컬 nginx(80) HTTPS 프록시
# 브라우저가 https:// 로만 접속할 때 443 미개방으로 "접속 불가"가 나는 경우 복구용
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"
if ! command -v tailscale >/dev/null 2>&1; then
  echo "tailscale 없음" >&2
  exit 1
fi
sudo tailscale serve reset 2>/dev/null || true
sudo tailscale serve --bg --https=443 http://127.0.0.1:80
sudo tailscale serve status
echo "OK: https://<magicdns>/ → nginx :80 (tailnet 전용)"
