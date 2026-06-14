#!/usr/bin/env bash
# DuckDNS IP 자동 갱신 (systemd timer, 10분마다)
# 사용: sudo bash ~/CronusFarm/scripts/pi-install-duckdns-autoupdate.sh
set -euo pipefail

CRONUS_ROOT="${CRONUS_ROOT:-$HOME/CronusFarm}"
ENV_EX="${CRONUS_ROOT}/deploy/env/duckdns.env.example"
ENV_DST="/etc/cronusfarm/duckdns.env"
UPDATE_SH="${CRONUS_ROOT}/scripts/pi-duckdns-update-ip.sh"
UNIT="/etc/systemd/system/cronusfarm-duckdns-update.service"
TIMER="/etc/systemd/system/cronusfarm-duckdns-update.timer"

if [[ ! -x "$UPDATE_SH" ]]; then
  chmod +x "$UPDATE_SH"
fi

sudo mkdir -p /etc/cronusfarm
if [[ ! -f "$ENV_DST" ]]; then
  if [[ ! -f "$ENV_EX" ]]; then
    echo "없음: $ENV_EX" >&2
    exit 1
  fi
  sudo cp "$ENV_EX" "$ENV_DST"
  echo "생성: $ENV_DST — DUCKDNS_TOKEN 을 넣은 뒤 이 스크립트를 다시 실행하세요."
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_DST"
if [[ -z "${DUCKDNS_TOKEN:-}" ]]; then
  echo "DUCKDNS_TOKEN 이 비어 있습니다: $ENV_DST" >&2
  echo "https://www.duckdns.org → cronusfarm → token 복사 후:" >&2
  echo "  sudo nano $ENV_DST" >&2
  exit 1
fi

NR_USER="$(systemctl show -p User --value nodered.service 2>/dev/null || echo dooly)"
sudo chown "root:${NR_USER}" "$ENV_DST" 2>/dev/null || sudo chown root:root "$ENV_DST"
sudo chmod 640 "$ENV_DST"

sudo tee "$UNIT" >/dev/null <<EOF
[Unit]
Description=CronusFarm DuckDNS IP update
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
EnvironmentFile=-$ENV_DST
ExecStart=$UPDATE_SH
EOF

sudo tee "$TIMER" >/dev/null <<EOF
[Unit]
Description=CronusFarm DuckDNS update timer

[Timer]
OnBootSec=2min
OnUnitActiveSec=10min
AccuracySec=1min

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now cronusfarm-duckdns-update.timer
bash "$UPDATE_SH"
echo "OK: DuckDNS timer active (10분). 최근 갱신: $(cat /var/log/cronusfarm-duckdns.log 2>/dev/null || echo done)"
