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

# 2) 브리지 응답 (3초 이내) + status API hang(장시간 빌드·lock) 감지
if ! curl -sf -m 3 -o /dev/null "$BRIDGE_URL/api/time/now"; then
  log "restart cronusfarm-sqlite-bridge (no /api/time/now)"
  sudo -n systemctl restart cronusfarm-sqlite-bridge.service 2>/dev/null || true
  sleep 2
elif ! curl -sf -m 5 -o /dev/null \
  "${BRIDGE_URL}/api/time/status?device_id=${CRONUSFARM_DEVICE_ID:-cronusfarm-01}"; then
  log "restart cronusfarm-sqlite-bridge (/api/time/status timeout)"
  sudo -n systemctl restart cronusfarm-sqlite-bridge.service 2>/dev/null || true
  sleep 2
fi
# 패널 펌웨어 빌드가 bridge 자식으로 붙으면 API가 막힘 — 30분 초과 시 종료
if pgrep -f 'pi-arduino-build\.sh.*CronusFarmPanel' >/dev/null 2>&1; then
  _build_age=$(ps -o etimes= -C bash 2>/dev/null | head -1 | tr -d ' ' || echo 0)
  if [[ "${_build_age:-0}" -ge 1800 ]]; then
    log "WARN panel build ${_build_age}s — stuck build SIGTERM"
    pkill -f 'pi-arduino-build\.sh.*CronusFarmPanel' 2>/dev/null || true
    sleep 2
    sudo -n systemctl restart cronusfarm-sqlite-bridge.service 2>/dev/null || true
  fi
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

# 4) AI 카메라 MJPEG — HEAD만 사용(무한 스트림 GET은 5s 타임아웃 → http_code 200 + || 000 이어붙여 200000 오판·2분마다 재시작)
_cam_code=000
if systemctl is-active --quiet cronusfarm-ustreamer.service 2>/dev/null \
   && systemctl is-active --quiet cronusfarm-hailo-stream.service 2>/dev/null; then
  _cam_code=$(curl -sS -m 3 -o /dev/null -w '%{http_code}' -I \
    http://127.0.0.1/farm/hailo-mjpeg/video_feed 2>/dev/null) || _cam_code=000
fi
if [[ "$_cam_code" != "200" ]]; then
  log "camera MJPEG HTTP ${_cam_code} — restart ustreamer/hailo"
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

# 6) R4 USB tele stale — 단계별 자동 복구 (serial→soft reset→업로드)
TELE_STALE_LIMIT="${CRONUSFARM_SITE_GUARD_TELE_STALE_SEC:-600}"
_status_json=$(curl -sf -m 6 \
  "${BRIDGE_URL}/api/time/status?device_id=${CRONUSFARM_DEVICE_ID:-cronusfarm-01}" 2>/dev/null || true)
if [[ -n "$_status_json" ]]; then
  _stale=$(printf '%s' "$_status_json" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(int(d.get('tele_stale_sec') or 0))" 2>/dev/null \
    || echo 0)
  if [[ "$_stale" -ge "$TELE_STALE_LIMIT" ]]; then
    log "R4 tele stale ${_stale}s (>=${TELE_STALE_LIMIT}) — escalate 복구"
    if [[ -x "$ROOT/scripts/pi-recover-r4-escalate.sh" ]]; then
      bash "$ROOT/scripts/pi-recover-r4-escalate.sh" >>"$LOG" 2>&1 || true
    fi
  fi

  # 7) R3 패널 I2C 미응답 — tele는 살아있고 r3_ok=false 30분+
  _r3_ok=$(printf '%s' "$_status_json" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print('1' if d.get('r3_ok') else '0')" 2>/dev/null || echo 1)
  _usb_on=$(printf '%s' "$_status_json" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print('1' if d.get('usb_online') else '0')" 2>/dev/null || echo 0)
  if [[ "$_usb_on" == "1" && "$_r3_ok" == "0" && "$_stale" -lt 120 ]]; then
    R3_STATE="/run/cronusfarm/r3-recover.last"
    R3_COOLDOWN="${CRONUSFARM_R3_RECOVER_COOLDOWN_SEC:-1800}"
    _now=$(date +%s)
    _last=0
    [[ -f "$R3_STATE" ]] && _last=$(cat "$R3_STATE" 2>/dev/null || echo 0)
    if [[ $((_now - _last)) -ge "$R3_COOLDOWN" ]] \
       && ! pgrep -f 'pi-arduino-build\.sh.*CronusFarmPanel' >/dev/null 2>&1; then
      log "R3 I2C 미응답 — 패널 소프트 리셋"
      if [[ -x "$ROOT/scripts/pi-reset-r3-soft.sh" ]]; then
        bash "$ROOT/scripts/pi-reset-r3-soft.sh" >>"$LOG" 2>&1 || true
      fi
      echo "$_now" | sudo tee "$R3_STATE" >/dev/null 2>&1 || true
    fi
  fi

  # 8) WiFi 프로비저닝 — MQTT farm 경로일 때만 (USB primary면 W:ip=0 정상, 시리얼 간섭 방지)
  _usb_primary="${CRONUSFARM_USB_PRIMARY:-1}"
  if [[ "$_usb_primary" != "1" && "$_usb_on" == "1" && "$_stale" -lt 120 ]]; then
    _tele_raw=$(curl -sf -m 5 \
      "${BRIDGE_URL}/api/tele/last?device_id=${CRONUSFARM_DEVICE_ID:-cronusfarm-01}" 2>/dev/null \
      | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('raw') or '')" 2>/dev/null || true)
    if [[ -n "$_tele_raw" ]] && echo "$_tele_raw" | grep -qE 'W:.*ip=0\.0\.0\.0'; then
      WIFI_STATE="/run/cronusfarm/wifi-recover.last"
      WIFI_COOLDOWN="${CRONUSFARM_WIFI_RECOVER_COOLDOWN_SEC:-1800}"
      _now=$(date +%s)
      _last=0
      [[ -f "$WIFI_STATE" ]] && _last=$(cat "$WIFI_STATE" 2>/dev/null || echo 0)
      if [[ $((_now - _last)) -ge "$WIFI_COOLDOWN" ]]; then
        log "WiFi ip=0.0.0.0 — 시리얼 프로비저닝"
        if [[ -f "$ROOT/scripts/cronusfarm_mqtt_wifi_recover.py" ]]; then
          python3 "$ROOT/scripts/cronusfarm_mqtt_wifi_recover.py" >>"$LOG" 2>&1 || true
        fi
        echo "$_now" | sudo tee "$WIFI_STATE" >/dev/null 2>&1 || true
      fi
    fi
  fi
fi

log "guard ok"
