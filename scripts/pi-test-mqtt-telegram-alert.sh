#!/usr/bin/env bash
# Pi: MQTT 감시 텔레그램 테스트 (수동 1회 발송)
set -euo pipefail
ROOT="${CRONUSFARM_ROOT:-$HOME/CronusFarm}"
sudo bash -lc "set -a; [ -f /etc/cronusfarm/nodered-telegram.env ] && . /etc/cronusfarm/nodered-telegram.env; set +a; python3 -c \"
import sys
sys.path.insert(0, '$ROOT/scripts')
import cronusfarm_mqtt_watch as w
t,c = w.resolve_telegram_creds()
print('token', len(t), 'chat', len(c))
ok = w.telegram_send(t, c, 'CronusFarm MQTT 알림 테스트 (수동)') if t and c else False
print('sent', ok)
sys.exit(0 if ok else 1)
\""
