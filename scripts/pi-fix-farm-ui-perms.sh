#!/usr/bin/env bash
# farm-ui 403 (nginx Permission denied) — rsync 후 farm-ui/ 가 700이면 www-data가 dist에 못 들어감
set -euo pipefail
ROOT="${CRONUSFARM_ROOT:-$HOME/CronusFarm}"
UI="$ROOT/farm-ui"
DIST="$UI/dist"
chmod a+x "$UI" 2>/dev/null || sudo chmod a+x "$UI"
chmod -R a+rX "$DIST"
# 홈·저장소 traverse (선택, 환경에 따라 이미 o+x)
chmod o+x "$HOME" "$ROOT" 2>/dev/null || sudo chmod o+x "$HOME" "$ROOT" 2>/dev/null || true
echo "OK: $DIST (nginx www-data 읽기 가능)"
