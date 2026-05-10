#!/bin/bash
# Pi에서 실행: nodered.service 에 텔레그램 환경변수 파일 연결
# - drop-in: EnvironmentFile=/etc/cronusfarm/nodered-telegram.env
# - 최초만 env 파일 생성(비어 있음). 값은 sudo nano /etc/cronusfarm/nodered-telegram.env
#
# 사용: bash ~/CronusFarm/scripts/pi-install-nodered-telegram-env.sh

set -eu

ROOT="${CRONUSFARM_ROOT:-$HOME/CronusFarm}"
DROPIN_SRC="${ROOT}/deploy/systemd/nodered.service.d/10-cronusfarm-telegram.conf"
ENV_EXAMPLE="${ROOT}/deploy/env/nodered-telegram.env.example"
ENV_DST="/etc/cronusfarm/nodered-telegram.env"

if [[ ! -f "$DROPIN_SRC" ]]; then
  echo "없음: $DROPIN_SRC (저장소 경로 확인)" >&2
  exit 1
fi
if [[ ! -f "$ENV_EXAMPLE" ]]; then
  echo "없음: $ENV_EXAMPLE" >&2
  exit 1
fi

sudo mkdir -p /etc/cronusfarm /etc/systemd/system/nodered.service.d
sudo cp -f "$DROPIN_SRC" /etc/systemd/system/nodered.service.d/10-cronusfarm-telegram.conf

if [[ ! -f "$ENV_DST" ]]; then
  sudo cp "$ENV_EXAMPLE" "$ENV_DST"
  sudo chmod 600 "$ENV_DST"
  sudo chown root:root "$ENV_DST"
  echo "생성: $ENV_DST — BotFather 토큰·chat_id 를 넣은 뒤: sudo systemctl restart nodered.service"
else
  echo "유지: $ENV_DST (이미 있음)"
fi

sudo systemctl daemon-reload
sudo systemctl restart nodered.service
echo "OK: nodered drop-in 적용 및 서비스 재시작"
