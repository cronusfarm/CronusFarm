#!/bin/bash
# Pi에서 실행: node-red-dashboard dist/mega.html 교체 (백업 포함, 최초 파일 없으면 백업 생략)
# 사용: ./pi-nodered-dashboard-apply-mega.sh /path/to/mega.html
set -eu

NEW_FILE="${1:?첫 인자: 소스 mega.html 경로}"
if [[ ! -f "$NEW_FILE" ]]; then
  echo "파일 없음: $NEW_FILE" >&2
  exit 1
fi

DIST="/home/dooly/.node-red/node_modules/node-red-dashboard/dist"
TARGET="$DIST/mega.html"

if [[ ! -d "$DIST" ]]; then
  echo "node-red-dashboard dist 경로 없음: $DIST" >&2
  exit 1
fi

if [[ -f "$TARGET" ]]; then
  TS="$(date +%s)"
  cp "$TARGET" "$TARGET.cronusfarm-backup.$TS"
  echo "백업: $TARGET.cronusfarm-backup.$TS"
else
  echo "참고: 기존 mega.html 없음 — 신규 배치합니다."
fi

cp "$NEW_FILE" "$TARGET"
echo "적용: $TARGET"
echo "완료"
