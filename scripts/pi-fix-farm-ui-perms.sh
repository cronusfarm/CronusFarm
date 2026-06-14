#!/usr/bin/env bash
# farm-ui 403 (nginx Permission denied) — rsync 후 farm-ui/ 가 700이면 www-data가 dist에 못 들어감
set -euo pipefail
ROOT="${CRONUSFARM_ROOT:-$HOME/CronusFarm}"
UI="$ROOT/farm-ui"
DIST="$UI/dist"
# rsync/scp 후 farm-ui(705)·dist(700) 이면 www-data → 403
chmod a+rx "$UI" 2>/dev/null || sudo chmod a+rx "$UI"
chmod -R a+rX "$DIST"
# 홈·저장소 traverse (nginx www-data)
chmod o+x "$HOME" "$ROOT" 2>/dev/null || sudo chmod o+x "$HOME" "$ROOT" 2>/dev/null || true
sudo chmod o+rx "$UI" 2>/dev/null || chmod o+rx "$UI" 2>/dev/null || true
if ! sudo -u www-data test -r "$DIST/index.html" 2>/dev/null; then
  echo "WARN: www-data 가 index.html 을 읽지 못함 — ls -la $UI $DIST" >&2
  ls -ld "$UI" "$DIST" 2>/dev/null || true
  exit 1
fi
echo "OK: $DIST (nginx www-data 읽기 가능)"
