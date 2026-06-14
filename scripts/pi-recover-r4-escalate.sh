#!/usr/bin/env bash
# R4 tele stale 단계별 자동 복구 (site-guard·mqtt-watch)
#  T1: serial 데몬 재시작 + SCHED/RTC
#  T2: R4 소프트 리셋
#  T3: R4 펌웨어 재업로드
set -euo pipefail

ROOT="${CRONUSFARM_ROOT:-$HOME/CronusFarm}"
DEVICE_ID="${CRONUSFARM_DEVICE_ID:-cronusfarm-01}"
BRIDGE_URL="${CRONUSFARM_BRIDGE_URL:-http://127.0.0.1:18766}"
STATE="${CRONUSFARM_R4_RECOVER_STATE:-/run/cronusfarm/r4-recover.state}"
LOG="${CRONUSFARM_R4_RECOVER_LOG:-/tmp/cronusfarm-r4-recover.log}"

T1="${CRONUSFARM_R4_RECOVER_T1_SEC:-600}"
T2="${CRONUSFARM_R4_RECOVER_T2_SEC:-900}"
T3="${CRONUSFARM_R4_RECOVER_T3_SEC:-1200}"
OK_STALE="${CRONUSFARM_RECOVER_TELE_MAX_STALE_SEC:-90}"
STEP_COOLDOWN="${CRONUSFARM_R4_RECOVER_STEP_COOLDOWN_SEC:-300}"
STEP_FAIL_BUMP="${CRONUSFARM_R4_RECOVER_FAIL_BUMP:-1}"

log() { echo "$(date '+%F %T') [r4-escalate] $*" | tee -a "$LOG"; }

fetch_status() {
  curl -sf -m 6 "${BRIDGE_URL}/api/time/status?device_id=${DEVICE_ID}" 2>/dev/null || true
}

get_stale() {
  local j
  j="$(fetch_status)"
  [[ -z "$j" ]] && echo -1 && return 0
  printf '%s' "$j" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(int(d.get('tele_stale_sec') or 99999))" \
    2>/dev/null || echo 99999
}

read_state() {
  if [[ -f "$STATE" ]]; then
    # shellcheck disable=SC1090
    source "$STATE" 2>/dev/null || true
  fi
  echo "${step:-0} ${last_at:-0} ${last_ok:-0}"
}

write_state() {
  local s="$1" t="$2" ok="${3:-0}"
  sudo mkdir -p "$(dirname "$STATE")"
  printf 'step=%s\nlast_at=%s\nlast_ok=%s\n' "$s" "$t" "$ok" | sudo tee "$STATE" >/dev/null
}

clear_state() {
  sudo rm -f "$STATE" 2>/dev/null || true
}

stale="$(get_stale)"
if [[ "$stale" -lt 0 ]]; then
  log "bridge API 없음 — sqlite-bridge 재시작 시도"
  sudo -n systemctl restart cronusfarm-sqlite-bridge.service 2>/dev/null || true
  sleep 3
  stale="$(get_stale)"
fi

if [[ "$stale" -ge 0 && "$stale" -lt "$OK_STALE" ]]; then
  clear_state
  exit 0
fi

read -r step last_at last_ok < <(read_state)
now=$(date +%s)
if [[ "$last_at" -gt 0 && $((now - last_at)) -lt "$STEP_COOLDOWN" ]]; then
  log "cooldown ${STEP_COOLDOWN}s (stale=${stale}s step=${step})"
  exit 0
fi

target=0
if [[ "$stale" -ge "$T3" ]]; then target=3
elif [[ "$stale" -ge "$T2" ]]; then target=2
elif [[ "$stale" -ge "$T1" ]]; then target=1
else
  exit 0
fi

if [[ "$target" -lt "$step" ]]; then
  step=0
  last_ok=0
fi
# 같은 step을 이미 성공했을 때만 스킵 (실패 후에는 cooldown 뒤 재시도)
if [[ "$target" -eq "$step" && "$target" -lt 3 && "${last_ok:-0}" == "1" ]]; then
  log "step ${step} 성공 이력 — stale=${stale}s (다음 단계 대기)"
  exit 0
fi
# 실패 후 stale가 더 커지면 한 단계 올려 재시도 (STEP1 고착 방지)
if [[ "$STEP_FAIL_BUMP" == "1" && "$target" -eq "$step" && "${last_ok:-0}" == "0" && "$step" -lt 3 ]]; then
  target=$((step + 1))
  log "step ${step} 이전 실패 — target→${target} (stale=${stale}s)"
fi

do_step1() {
  log "STEP1 stale=${stale}s — serial 재시작 + reboot cmd + SCHED/RTC"
  sudo -n systemctl restart cronusfarm-r4-serial.service 2>/dev/null || true
  sleep 3
  curl -sf -m 8 -X POST "http://127.0.0.1:18767/r4/cmd" \
    -H 'Content-Type: application/json' \
    -d '{"payload":"reboot=1"}' >>"$LOG" 2>&1 || true
  sleep 8
  if [[ -x "$ROOT/scripts/pi-sync-schedules-serial.sh" ]]; then
    bash "$ROOT/scripts/pi-sync-schedules-serial.sh" >>"$LOG" 2>&1 || true
  fi
  if [[ -x "$ROOT/scripts/pi-mqtt-publish-rtc-to-r4.sh" ]]; then
    CRONUSFARM_R4_CMD_TRANSPORT=serial bash "$ROOT/scripts/pi-mqtt-publish-rtc-to-r4.sh" >>"$LOG" 2>&1 || true
  fi
}

do_step2() {
  log "STEP2 stale=${stale}s — R4 소프트 리셋"
  if [[ -x "$ROOT/scripts/pi-reset-r4.sh" ]]; then
    bash "$ROOT/scripts/pi-reset-r4.sh" >>"$LOG" 2>&1 || true
  fi
  sleep 18
}

do_step3() {
  log "STEP3 stale=${stale}s — R4 펌웨어 재업로드"
  if [[ -x "$ROOT/scripts/pi-upload-r4.sh" ]]; then
    # site-guard 등 HOME 미설정 시 bossac 탐색 실패 방지
    HOME="${HOME:-$(getent passwd dooly 2>/dev/null | cut -d: -f6)}"
    HOME="${HOME:-/home/dooly}"
    HOME="$HOME" USER="${USER:-dooly}" bash "$ROOT/scripts/pi-upload-r4.sh" >>"$LOG" 2>&1 || true
  fi
  sleep 12
  sudo -n systemctl restart cronusfarm-r4-serial.service 2>/dev/null || true
}

case "$target" in
  1) do_step1 ;;
  2) do_step2 ;;
  3) do_step3 ;;
esac

sleep 12
stale2="$(get_stale)"
if [[ "$stale2" -ge 0 && "$stale2" -lt "$OK_STALE" ]]; then
  log "복구 성공 tele_stale=${stale2}s (step ${target})"
  clear_state
  exit 0
fi
write_state "$target" "$now" 0
log "복구 진행 중 tele_stale=${stale2}s (step ${target} 완료, 실패→재시도 허용)"
exit 0
