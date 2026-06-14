#!/bin/bash
# Pi에서 실행: node-red-dashboard dist/index.html을 교체 (백업 포함)
# 사용: ./pi-nodered-dashboard-apply-index.sh /path/to/index.html
set -eu

NEW_INDEX="${1:?첫 인자: 새 index.html 경로}"
if [[ ! -f "$NEW_INDEX" ]]; then
  echo "파일 없음: $NEW_INDEX" >&2
  exit 1
fi

DIST="/home/dooly/.node-red/node_modules/node-red-dashboard/dist"
TARGET="$DIST/index.html"

if [[ ! -d "$DIST" ]]; then
  echo "node-red-dashboard dist 경로 없음: $DIST" >&2
  exit 1
fi
if [[ ! -f "$TARGET" ]]; then
  echo "기존 index.html 없음: $TARGET" >&2
  exit 1
fi

TS="$(date +%s)"
cp "$TARGET" "$TARGET.cronusfarm-backup.$TS"
echo "백업: $TARGET.cronusfarm-backup.$TS"

cp "$NEW_INDEX" "$TARGET"
echo "적용: $TARGET"

echo "완료"

