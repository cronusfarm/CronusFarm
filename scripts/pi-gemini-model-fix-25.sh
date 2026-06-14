#!/bin/bash
# Pi: 텔레그램 비전 Gemini 모델을 2.5-flash-lite 로 맞춤 (2.0 무료 한도 0 회피)
set -eu
ENV=/etc/cronusfarm/nodered-telegram.env
if [[ ! -f "$ENV" ]]; then
  echo "없음: $ENV" >&2
  exit 1
fi
sudo sed -i 's/\r$//' "$ENV"
if grep -q '^CRONUSFARM_GEMINI_MODEL=' "$ENV"; then
  sudo sed -i 's/^CRONUSFARM_GEMINI_MODEL=.*/CRONUSFARM_GEMINI_MODEL=gemini-2.5-flash-lite/' "$ENV"
else
  echo 'CRONUSFARM_GEMINI_MODEL=gemini-2.5-flash-lite' | sudo tee -a "$ENV" >/dev/null
fi
if grep -q '^CRONUSFARM_GEMINI_FALLBACK_MODELS=' "$ENV"; then
  sudo sed -i 's|^CRONUSFARM_GEMINI_FALLBACK_MODELS=.*|CRONUSFARM_GEMINI_FALLBACK_MODELS=gemini-flash-lite-latest,gemini-2.5-flash-lite,gemini-2.0-flash-lite|' "$ENV"
else
  echo 'CRONUSFARM_GEMINI_FALLBACK_MODELS=gemini-flash-lite-latest,gemini-2.5-flash-lite,gemini-2.0-flash-lite' | sudo tee -a "$ENV" >/dev/null
fi
grep '^CRONUSFARM_GEMINI_' "$ENV" | sed 's/=.*/=***/'
echo "nodered 재시작…"
sudo systemctl restart nodered.service
echo "완료"
