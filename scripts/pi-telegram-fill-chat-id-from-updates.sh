#!/bin/bash
# Pi에서 실행: /etc/cronusfarm/nodered-telegram.env 의 토큰으로 getUpdates 해서
# 마지막 메시지의 chat_id 를 CHAT_ID 줄에 넣고 nodered 재시작.
# 전제: 사용자가 봇에게 이미 /start 등 메시지를 보낸 상태.
set -euo pipefail
ENV=/etc/cronusfarm/nodered-telegram.env
if [[ ! -f "$ENV" ]]; then echo "없음: $ENV" >&2; exit 1; fi
# 파일이 root 600 이라 source 불가 — 토큰 줄만 sudo 로 읽음
TOK=$(sudo grep -m1 '^CRONUSFARM_TELEGRAM_BOT_TOKEN=' "$ENV" | cut -d= -f2- | tr -d '\r' | sed "s/^['\"]//;s/['\"]$//")
if [[ -z "$TOK" ]]; then echo "CRONUSFARM_TELEGRAM_BOT_TOKEN 비어 있음(또는 읽기 실패)" >&2; exit 1; fi
# 웹훅이 잡혀 있으면 getUpdates 가 비어 있음 → 폴링으로 chat_id 뽑을 때만 제거
WH=$(curl -sS "https://api.telegram.org/bot${TOK}/getWebhookInfo")
WURL=$(echo "$WH" | jq -r '.result.url // empty')
if [[ -n "$WURL" ]]; then
  echo "웹훅 제거(폴링): $WURL" >&2
  curl -sS "https://api.telegram.org/bot${TOK}/deleteWebhook?drop_pending_updates=false" | jq -e '.ok == true' >/dev/null
fi
RAW=$(curl -sS "https://api.telegram.org/bot${TOK}/getUpdates")
CID=$(echo "$RAW" | jq -r "[.result[]? | select(.message.chat.id != null) | .message.chat.id] | last // empty")
if [[ -z "$CID" || "$CID" == "null" ]]; then
  echo "getUpdates에 대화 없음. 텔레그램 앱에서 봇에게 /start 를 보낸 뒤 다시 실행하세요." >&2
  exit 2
fi
sudo sed -i "/^CRONUSFARM_TELEGRAM_CHAT_ID=/d" "$ENV"
echo "CRONUSFARM_TELEGRAM_CHAT_ID=$CID" | sudo tee -a "$ENV" >/dev/null
sudo chmod 600 "$ENV"
echo "OK CRONUSFARM_TELEGRAM_CHAT_ID=$CID"
sudo systemctl restart nodered.service
echo "OK nodered.service restarted"
