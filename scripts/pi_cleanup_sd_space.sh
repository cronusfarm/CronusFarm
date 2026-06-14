#!/usr/bin/env bash
# Pi: SD 불필요 파일 정리 + DB 심볼릭 링크 복구
set -euo pipefail

BAK="/home/dooly/.node-red/cronusfarm.sqlite.sd-bak-1781142131"
USB="/mnt/usb/cronusfarm/cronusfarm.sqlite"
LINK="/home/dooly/.node-red/cronusfarm.sqlite"
MIN_BYTES=104857600

log() { echo "[cleanup-sd] $*"; }

log "=== before ==="
df -h /

usb_ok=0
if [[ -f "$USB" ]]; then
  sz="$(stat -c%s "$USB")"
  if (( sz > MIN_BYTES )); then
    cnt="$(sqlite3 "$USB" "SELECT COUNT(*) FROM tele_sample;" 2>/dev/null || echo 0)"
    [[ "$cnt" -gt 0 ]] && usb_ok=1
  fi
  log "USB DB size=${sz} ok=${usb_ok}"
else
  log "USB DB 없음"
fi

log "flow 백업 삭제"
rm -f /home/dooly/.node-red/flows.cronusfarm-backup.* 2>/dev/null || true

log "boot.log 삭제"
sudo rm -f /var/log/boot.log.[0-9]* /var/log/boot.log.10 2>/dev/null || true

log "apt cache 정리"
sudo apt-get clean 2>/dev/null || true

log "USB migrate tmp/깨진 파일 정리"
rm -rf /mnt/usb/cronusfarm/tmp 2>/dev/null || true

if (( usb_ok == 1 )); then
  log "USB 백업 유효 — SD 백업 삭제"
  rm -f "${BAK}" "${BAK}-wal" "${BAK}-shm"
  rm -f "$LINK"
  ln -sfn "$USB" "$LINK"
else
  log "USB 백업 미완료 — SD 백업 유지, 링크 복구"
  rm -f /mnt/usb/cronusfarm/cronusfarm.sqlite \
        /mnt/usb/cronusfarm/cronusfarm.sqlite-wal \
        /mnt/usb/cronusfarm/cronusfarm.sqlite-shm \
        /mnt/usb/cronusfarm/cronusfarm.sqlite-journal 2>/dev/null || true
  rm -f "$LINK"
  ln -sfn "$BAK" "$LINK"
fi

TARGET="$(readlink -f "$LINK")"
if [[ -f /etc/systemd/system/cronusfarm-sqlite-bridge.service ]]; then
  sudo sed -i "s|Environment=CRONUSFARM_SQLITE_PATH=.*|Environment=CRONUSFARM_SQLITE_PATH=$TARGET|" \
    /etc/systemd/system/cronusfarm-sqlite-bridge.service
  sudo systemctl daemon-reload
fi
if [[ -f /etc/cronusfarm/cctv.env ]] && grep -q CRONUSFARM_SQLITE_PATH /etc/cronusfarm/cctv.env; then
  sudo sed -i "s|^CRONUSFARM_SQLITE_PATH=.*|CRONUSFARM_SQLITE_PATH=$TARGET|" /etc/cronusfarm/cctv.env
fi

sudo systemctl restart cronusfarm-sqlite-bridge 2>/dev/null || true

log "=== after ==="
df -h /
ls -la "$LINK"
du -sh "${BAK}"* 2>/dev/null || log "SD 백업 파일 없음 (USB 이전 완료)"
curl -sf "http://127.0.0.1:18766/health" >/dev/null && log "bridge OK" || log "WARN bridge"
