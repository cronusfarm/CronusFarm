#!/usr/bin/env bash
set -euo pipefail

# CronusFarm Pi AI 사전 준비 스크립트(요약):
# - IP 카메라(RTSP) 기반 추론 서비스는 별도(추후 Hailo 장착 후 구성)
# - Node-RED는 결과 저장/알림/대시보드 담당
# - LLM은 Ollama로 설치(질문/알림 생성용)
#
# 사용:
#   bash ~/CronusFarm/scripts/pi-ai-setup.sh
#
# 주의:
# - 네트워크/배포판에 따라 패키지명이 다를 수 있습니다.
# - Hailo 런타임/컴파일러는 별도 설치(벤더 문서 기준)입니다.

echo "=== apt 기본 패키지 ==="
sudo apt update
sudo apt install -y curl jq sqlite3 mosquitto-clients

echo "=== Ollama 설치 ==="
if command -v ollama >/dev/null 2>&1; then
  echo "Ollama: already installed"
else
  curl -fsSL https://ollama.com/install.sh | sh
fi

echo "=== Ollama 서비스 시작 ==="
sudo systemctl enable --now ollama || true
sleep 1
ollama --version || true

echo "=== Gemma 2B 다운로드(가능한 이름 시도) ==="
if ollama list 2>/dev/null | grep -qE '^gemma:2b\s'; then
  echo "gemma:2b already present"
else
  ollama pull gemma:2b || true
fi
if ! ollama list 2>/dev/null | grep -qE '^gemma:2b\s'; then
  # 일부 환경에서는 이름이 다를 수 있어 대체 후보를 시도
  ollama pull gemma2:2b || true
fi

echo "=== Node-RED 노드 설치(옵션) ==="
NR_DIR="${HOME}/.node-red"
if [ -d "${NR_DIR}" ]; then
  cd "${NR_DIR}"
  npm i node-red-contrib-telegrambot node-red-node-sqlite
  sudo systemctl restart nodered.service || true
else
  echo "skip: ~/.node-red not found (Node-RED 미설치/경로 다름)"
fi

echo "OK: AI 준비 완료(추론 파이프라인은 별도 구성)"

