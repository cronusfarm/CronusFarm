#!/usr/bin/env bash
#
# Pi → R4 RTC MQTT 동기 systemd 타이머 설치(5분마다 rtc_local 발행)
#
# 사용:
#   sudo bash ./pi-install-mqtt-rtc-r4-timer.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_DIR="/etc/systemd/system"
SVC="cronusfarm-mqtt-rtc-r4.service"
TMR="cronusfarm-mqtt-rtc-r4.timer"

cat >"/tmp/$SVC" <<EOF
[Unit]
Description=CronusFarm Pi local time to R4 RTC (MQTT rtc_local)
After=network.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/env bash ${ROOT}/scripts/pi-mqtt-publish-rtc-to-r4.sh

[Install]
WantedBy=multi-user.target
EOF

cat >"/tmp/$TMR" <<'EOF'
[Unit]
Description=Timer — CronusFarm R4 RTC sync via MQTT

[Timer]
OnBootSec=90
OnUnitActiveSec=5min
AccuracySec=30
Unit=cronusfarm-mqtt-rtc-r4.service

[Install]
WantedBy=timers.target
EOF

install -m 0644 "/tmp/$SVC" "$UNIT_DIR/$SVC"
install -m 0644 "/tmp/$TMR" "$UNIT_DIR/$TMR"
systemctl daemon-reload
systemctl enable "$TMR"
systemctl start "$TMR"
systemctl start "$SVC" || true

echo "[ok] timer: $TMR (5min) + oneshot service: $SVC"
systemctl --no-pager --full status "$TMR" || true
