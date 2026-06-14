#!/bin/bash
# Pi: 1880 이 nginx 이고 /ui 가 502 일 때 — NR 이 업스트림(기본 1882)에서 안 떠 있는 전형적 원인 보정
# nginx 없거나 1880 이 nginx가 아니면 아무 것도 안 함
set -eu
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"

UPSTREAM_PORT="${CRONUSFARM_NR_UPSTREAM_PORT:-1882}"

is_nginx_on_1880() {
  local srv
  srv="$(curl -sSI --max-time 2 "http://127.0.0.1:1880/" 2>/dev/null | grep -i '^Server:' | head -1 | tr -d '\r' || true)"
  echo "$srv" | grep -qi nginx
}

upstream_listening() {
  ss -tlnp 2>/dev/null | grep -F ":${UPSTREAM_PORT}" | grep -q . || return 1
  return 0
}

if [[ ! -x /usr/sbin/nginx ]] && ! command -v nginx >/dev/null 2>&1; then
  echo "OK: nginx not installed — skip upstream fix"
  exit 0
fi

if ! is_nginx_on_1880; then
  echo "OK: :1880 is not nginx front — skip upstream fix"
  exit 0
fi

if upstream_listening; then
  echo "OK: Node-RED upstream :${UPSTREAM_PORT} already listening"
  exit 0
fi

echo "WARN: nginx on :1880 but nothing on :${UPSTREAM_PORT} (502 cause). Applying nodered PORT=${UPSTREAM_PORT}" >&2

if ! sudo -n true 2>/dev/null; then
  echo "Need sudo. On Pi run:" >&2
  echo "  sudo mkdir -p /etc/systemd/system/nodered.service.d" >&2
  echo "  printf '%s\\n' '[Service]' 'Environment=PORT=${UPSTREAM_PORT}' | sudo tee /etc/systemd/system/nodered.service.d/cronusfarm-port.conf" >&2
  echo "  sudo systemctl daemon-reload && sudo systemctl restart nodered.service" >&2
  exit 0
fi

sudo mkdir -p /etc/systemd/system/nodered.service.d
sudo tee /etc/systemd/system/nodered.service.d/cronusfarm-port.conf >/dev/null <<EOF
[Service]
Environment=PORT=${UPSTREAM_PORT}
EOF
sudo systemctl daemon-reload
sudo systemctl restart nodered.service
sleep 3

code="$(curl -sS -o /dev/null -w "%{http_code}" --max-time 5 "http://127.0.0.1:1880/ui/" 2>/dev/null || echo 000)"
echo "After restart: GET http://127.0.0.1:1880/ui/ -> HTTP ${code}" >&2
if [[ "$code" == "502" ]]; then
  echo "WARN: still 502 — journalctl -u nodered -n 80; ss -tlnp | grep -E '1880|1882'" >&2
fi
