#!/usr/bin/env bash
# CronusFarm 사이트 접속 자동 복구 — farm-ui 403·NR 1882·브리지 18766
# systemd timer 로 2분마다 실행 권장
set -euo pipefail

ROOT="${CRONUSFARM_ROOT:-$HOME/CronusFarm}"
LOG="${CRONUSFARM_SITE_GUARD_LOG:-/tmp/cronusfarm-site-guard.log}"
BRIDGE_URL="${CRONUSFARM_BRIDGE_URL:-http://127.0.0.1:18766}"
UI_URL="${CRONUSFARM_UI_URL:-http://127.0.0.1:1882/ui/}"
FARM_JS="${CRONUSFARM_FARM_UI_JS:-}"

log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }

# 1) farm-ui nginx 읽기 권한 (scp 후 700 → 403)
if [[ -x "$ROOT/scripts/pi-fix-farm-ui-perms.sh" ]]; then
  if ! sudo -u www-data test -r "$ROOT/farm-ui/dist/index.html" 2>/dev/null; then
    log "fix farm-ui perms"
    bash "$ROOT/scripts/pi-fix-farm-ui-perms.sh" >>"$LOG" 2>&1 || true
  fi
fi

# 2) 브리지 응답 (3초 이내)
if ! curl -sf -m 3 -o /dev/null "$BRIDGE_URL/api/time/now"; then
  log "restart cronusfarm-sqlite-bridge (no /api/time/now)"
  sudo -n systemctl restart cronusfarm-sqlite-bridge.service 2>/dev/null || true
  sleep 2
fi

# 3) Node-RED 1882
if ! curl -sf -m 5 -o /dev/null "$UI_URL"; then
  log "restart nodered (ui down)"
  sudo -n systemctl restart nodered.service 2>/dev/null || true
  if [[ -x "$ROOT/scripts/pi-nodered-wait-ready.sh" ]]; then
    bash "$ROOT/scripts/pi-nodered-wait-ready.sh" 90 >>"$LOG" 2>&1 || true
  else
    sleep 15
  fi
fi

# 4) AI 카메라 MJPEG (nginx → hailo 8081 / ustreamer 8080)
_cam_code=$(curl -sS -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1/farm/hailo-mjpeg/video_feed 2>/dev/null || echo 000)
if [[ "$_cam_code" != "200" ]]; then
  log "camera MJPEG HTTP $_cam_code — restart ustreamer/hailo"
  sudo -n systemctl restart cronusfarm-ustreamer.service 2>/dev/null || true
  sudo -n systemctl restart cronusfarm-hailo-stream.service 2>/dev/null || true
  sleep 3
fi

# 5) farm-ui JS 번들 HTTP (선택)
if [[ -z "$FARM_JS" && -f "$ROOT/farm-ui/dist/index.html" ]]; then
  FARM_JS=$(grep -oE 'assets/index-[^"]+\.js' "$ROOT/farm-ui/dist/index.html" | head -1 || true)
fi
if [[ -n "$FARM_JS" ]]; then
  code=$(curl -sS -m 5 -o /dev/null -w '%{http_code}' "http://127.0.0.1/farm/ui/$FARM_JS" || echo 000)
  if [[ "$code" != "200" ]]; then
    log "farm-ui JS HTTP $code — perms 재시도"
    bash "$ROOT/scripts/pi-fix-farm-ui-perms.sh" >>"$LOG" 2>&1 || true
  fi
fi

log "guard ok"
