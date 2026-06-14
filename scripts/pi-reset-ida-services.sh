#!/usr/bin/env bash
# ida(Pi) 웹·NR·브리지 재시작 (nginx 80 복구용)
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"
restart_one() {
  if sudo -n systemctl restart "$1" 2>/dev/null; then
    echo "OK restart $1"
  elif systemctl --user restart "$1" 2>/dev/null; then
    echo "OK user restart $1"
  else
    echo "WARN skip $1 (no sudo)"
  fi
}
restart_one nginx
restart_one nodered.service
restart_one cronusfarm-sqlite-bridge.service
if sudo -n nginx -t 2>/dev/null; then
  sudo -n systemctl reload nginx 2>/dev/null || true
fi
echo "DONE ida services"
