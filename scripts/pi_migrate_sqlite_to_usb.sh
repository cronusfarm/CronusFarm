#!/usr/bin/env bash
# Pi: cronusfarm.sqlite → /mnt/usb/cronusfarm/ 이전 (SD 여유 확보)
set -euo pipefail

USB_DIR="/mnt/usb/cronusfarm"
LINK_DB="${HOME}/.node-red/cronusfarm.sqlite"
NEW_DB="${USB_DIR}/cronusfarm.sqlite"
KEEP_DAYS="${CRONUSFARM_SQLITE_KEEP_DAYS:-7}"
SKIP_PRUNE="${CRONUSFARM_SQLITE_SKIP_PRUNE:-0}"
MIN_DB_BYTES="${CRONUSFARM_SQLITE_MIN_BYTES:-104857600}"  # 100MB 미만이면 실패로 간주

log() { echo "[migrate-sqlite] $*"; }

if [[ ! -d /mnt/usb ]]; then
  log "ERROR: /mnt/usb 미마운트"
  exit 1
fi

mkdir -p "$USB_DIR"

stop_writers() {
  log "서비스 중지..."
  sudo systemctl stop cronusfarm-cctv.service 2>/dev/null || true
  sudo systemctl stop cronusfarm-sqlite-bridge.service 2>/dev/null || true
  sudo systemctl stop nodered.service 2>/dev/null || true
  sleep 3
}

start_writers() {
  log "서비스 시작..."
  sudo systemctl start cronusfarm-sqlite-bridge.service
  sudo systemctl start nodered.service
  sudo systemctl start cronusfarm-cctv.service 2>/dev/null || true
}

db_bytes() {
  local p="$1" n=0 f
  for f in "$p" "$p-wal" "$p-shm" "$p-journal"; do
    [[ -f "$f" ]] && n=$((n + $(stat -c%s "$f")))
  done
  echo "$n"
}

usb_free_bytes() {
  df -B1 /mnt/usb | awk 'NR==2 {print $4}'
}

find_source_db() {
  # SD 백업이 있으면 그걸 소스로 (이전 실패 복구)
  local bak
  bak="$(ls -1t "${HOME}/.node-red/cronusfarm.sqlite.sd-bak-"* 2>/dev/null | grep -v '\-wal$' | grep -v '\-shm$' | head -1 || true)"
  if [[ -n "$bak" && -f "$bak" ]]; then
    fix_wal_names "$bak" >&2
    echo "$bak"
    return 0
  fi
  if [[ -f "$LINK_DB" && ! -L "$LINK_DB" ]]; then
    echo "$LINK_DB"
    return 0
  fi
  if [[ -L "$LINK_DB" ]]; then
    local tgt
    tgt="$(readlink -f "$LINK_DB" 2>/dev/null || true)"
    if [[ -n "$tgt" && -f "$tgt" && $(stat -c%s "$tgt") -ge "$MIN_DB_BYTES" ]]; then
      echo "$tgt"
      return 0
    fi
  fi
  if [[ -n "$bak" ]]; then
    echo "$bak"
    return 0
  fi
  echo "$LINK_DB"
}

fix_wal_names() {
  local main="$1"
  local dir base wal shm
  dir="$(dirname "$main")"
  base="$(basename "$main")"
  # 잘못된 백업명: cronusfarm.sqlite-wal.sd-bak-TS → cronusfarm.sqlite.sd-bak-TS-wal
  for wal in "${dir}/cronusfarm.sqlite-wal.sd-bak-"*; do
    [[ -f "$wal" ]] || continue
    local ts="${wal##*.sd-bak-}"
    local want="${dir}/cronusfarm.sqlite.sd-bak-${ts}-wal"
    [[ -f "$want" ]] || mv "$wal" "$want"
  done
  for shm in "${dir}/cronusfarm.sqlite-shm.sd-bak-"*; do
    [[ -f "$shm" ]] || continue
    local ts="${shm##*.sd-bak-}"
    local want="${dir}/cronusfarm.sqlite.sd-bak-${ts}-shm"
    [[ -f "$want" ]] || mv "$shm" "$want"
  done
  wal="${main}-wal"
  shm="${main}-shm"
  [[ -f "$wal" ]] || true
  [[ -f "$shm" ]] || true
}

prune_old_rows() {
  local src="$1"
  local days="$2"
  local cutoff_ms=$(( ($(date +%s) - days * 86400) * 1000 ))
  log "소스=${src} — ${days}일 이전 행 삭제"
  sqlite3 "$src" "PRAGMA wal_checkpoint(TRUNCATE);"
  rm -f "${src}-wal" "${src}-shm"
  sqlite3 "$src" <<SQL
BEGIN;
DELETE FROM tele_channel_fact WHERE ts_ms < ${cutoff_ms};
DELETE FROM tele_sample WHERE ts_ms < ${cutoff_ms};
DELETE FROM mqtt_status_log WHERE ts_ms < ${cutoff_ms};
DELETE FROM mqtt_cmd_log WHERE ts_ms < ${cutoff_ms};
COMMIT;
SQL
}

vacuum_into_usb() {
  local src="$1"
  local tmp="${USB_DIR}/tmp"
  mkdir -p "$tmp"
  export TMPDIR="$tmp"
  rm -f "$NEW_DB" "$NEW_DB-wal" "$NEW_DB-shm" "$NEW_DB-journal"
  log "VACUUM INTO ${src} → $NEW_DB (TMPDIR=$tmp)"
  sqlite3 "$src" "PRAGMA temp_store_directory='${tmp}'; VACUUM INTO '${NEW_DB}';"
  sqlite3 "$NEW_DB" "PRAGMA journal_mode=DELETE; PRAGMA synchronous=NORMAL;"
}

ensure_symlink() {
  rm -f "$LINK_DB"
  ln -sfn "$NEW_DB" "$LINK_DB"
  log "심볼릭 링크: $LINK_DB → $NEW_DB"
}

cleanup_sd_backup() {
  local f
  for f in "${HOME}/.node-red/cronusfarm.sqlite.sd-bak-"* \
           "${HOME}/.node-red/cronusfarm.sqlite-wal.sd-bak-"* \
           "${HOME}/.node-red/cronusfarm.sqlite-shm.sd-bak-"* \
           "${HOME}/.node-red/cronusfarm.sqlite.sd-bak-"*-wal \
           "${HOME}/.node-red/cronusfarm.sqlite.sd-bak-"*-shm; do
    [[ -e "$f" ]] || continue
    rm -v "$f"
  done
  log "SD 백업 파일 삭제 완료"
}

patch_systemd() {
  local svc="/etc/systemd/system/cronusfarm-sqlite-bridge.service"
  if [[ -f "$svc" ]]; then
    sudo sed -i "s|Environment=CRONUSFARM_SQLITE_PATH=.*|Environment=CRONUSFARM_SQLITE_PATH=$NEW_DB|" "$svc"
    sudo systemctl daemon-reload
    log "systemd bridge → $NEW_DB"
  fi
  local cctv="/etc/cronusfarm/cctv.env"
  if [[ -f "$cctv" ]] && grep -q '^CRONUSFARM_SQLITE_PATH=' "$cctv"; then
    sudo sed -i "s|^CRONUSFARM_SQLITE_PATH=.*|CRONUSFARM_SQLITE_PATH=$NEW_DB|" "$cctv"
    log "cctv.env → $NEW_DB"
  fi
}

verify() {
  log "검증..."
  ls -lh "$LINK_DB" "$NEW_DB" 2>/dev/null || true
  df -h / /mnt/usb
  local sz
  sz="$(stat -c%s "$NEW_DB" 2>/dev/null || echo 0)"
  if (( sz < MIN_DB_BYTES )); then
    log "ERROR: USB DB 너무 작음 (${sz}B)"
    return 1
  fi
  curl -sf "http://127.0.0.1:18766/health" >/dev/null && log "bridge /health OK" || log "WARN: bridge health 실패"
  return 0
}

try_migrate() {
  local src="$1"
  local days="$2"
  if [[ "$SKIP_PRUNE" != "1" ]]; then
    prune_old_rows "$src" "$days"
  else
    log "SKIP_PRUNE=1 — 삭제 생략, VACUUM만 수행"
    sqlite3 "$src" "PRAGMA wal_checkpoint(TRUNCATE);"
    rm -f "${src}-wal" "${src}-shm"
  fi
  vacuum_into_usb "$src"
  local out free
  out="$(db_bytes "$NEW_DB")"
  free="$(usb_free_bytes)"
  log "USB 대상=${out}B, USB여유=${free}B"
  if (( out < MIN_DB_BYTES || out + 52428800 >= free )); then
    return 1
  fi
  ensure_symlink
  return 0
}

free_sd_space() {
  rm -f "${HOME}/.node-red/flows.cronusfarm-backup."* 2>/dev/null || true
  sudo rm -f /var/log/boot.log.[0-9]* /var/log/boot.log.10 2>/dev/null || true
  sudo apt-get clean 2>/dev/null || true
  log "SD 여유: $(df -h / | awk 'NR==2{print $4}')"
}

main() {
  log "시작 (KEEP_DAYS=$KEEP_DAYS)"
  stop_writers
  free_sd_space

  rm -f "$NEW_DB" "$NEW_DB-wal" "$NEW_DB-shm" "$NEW_DB-journal"

  local src
  src="$(find_source_db)"
  log "소스 DB: $src ($(db_bytes "$src")B)"

  if [[ "$SKIP_PRUNE" == "1" ]]; then
    log "VACUUM 직행"
    if try_migrate "$src" "0"; then
      cleanup_sd_backup
      patch_systemd
      start_writers
      sleep 3
      verify && log "완료 (VACUUM 직행)" && return 0
    fi
    log "ERROR: VACUUM 실패"
    start_writers
    exit 1
  fi

  for days in "$KEEP_DAYS" 3 1; do
    log "시도: 보존 ${days}일"
    if try_migrate "$src" "$days"; then
      cleanup_sd_backup
      patch_systemd
      start_writers
      sleep 3
      verify && log "완료 (보존 ${days}일)" && return 0
    fi
    log "보존 ${days}일 실패 — 다음 단계"
    rm -f "$NEW_DB" "$NEW_DB-wal" "$NEW_DB-shm" "$NEW_DB-journal"
  done

  log "ERROR: USB 용량 부족. /mnt/usb/CCTV 정리 또는 더 큰 USB 필요."
  start_writers
  exit 1
}

main "$@"
