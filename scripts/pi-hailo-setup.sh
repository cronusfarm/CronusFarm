#!/usr/bin/env bash
# Pi: ~/CronusFarm/Hailo/best.hef 배치 후 Hailo GStreamer 스트림 서비스 준비
# 사용: bash ~/CronusFarm/scripts/pi-hailo-setup.sh
set -euo pipefail

CRONUS_ROOT="${CRONUSFARM_ROOT:-$HOME/CronusFarm}"
HAILO_DIR="${CRONUSFARM_HAILO_DIR:-$CRONUS_ROOT/Hailo}"
SCRIPTS="$CRONUS_ROOT/scripts"
SYS_YOLO="/usr/share/hailo-models/yolov8.json"
HEF="$HAILO_DIR/best.hef"
SVC_NAME="cronusfarm-hailo-stream.service"
SVC_SRC="$CRONUS_ROOT/deploy/systemd/$SVC_NAME"

echo "=== Hailo 디렉터리 ==="
mkdir -p "$HAILO_DIR"
ls -la "$HAILO_DIR" || true

if [[ ! -f "$HEF" ]]; then
  echo "ERROR: $HEF 없음. Windows에서:" >&2
  echo "  .\\scripts\\cronusfarm-hailo-prepare-best.ps1 -DeployToPi -HefOnly" >&2
  exit 1
fi
echo "OK: best.hef ($(du -h "$HEF" | awk '{print $1}'))"

if [[ ! -f "$HAILO_DIR/yolov8.json" ]]; then
  if [[ -f "$HAILO_DIR/../Hailo/yolov8.json" ]]; then
    : # repo 동기화 시 이미 있음
  elif [[ -f "$CRONUS_ROOT/Hailo/yolov8.json" ]]; then
    cp -f "$CRONUS_ROOT/Hailo/yolov8.json" "$HAILO_DIR/yolov8.json"
  elif [[ -f "$SYS_YOLO" ]]; then
    cp -f "$SYS_YOLO" "$HAILO_DIR/yolov8.json"
    echo "OK: yolov8.json ← $SYS_YOLO"
  else
  cat >"$HAILO_DIR/yolov8.json" <<'JSON'
{
  "detection_threshold": 0.35,
  "max_boxes": 50,
  "labels": ["tomato", "fig", "butterhead", "basil"]
}
JSON
    echo "OK: 기본 yolov8.json 생성 (libyolo_hailortpp — best.hef NMS 포함)"
  fi
fi

echo "=== Hailo 런타임 점검 ==="
missing=0
command -v gst-launch-1.0 >/dev/null || { echo "WARN: gst-launch-1.0 없음" >&2; missing=1; }
python3 -c "import hailo" 2>/dev/null || {
  echo "WARN: python3 hailo 모듈 없음 (python3-hailo-tappas 설치 필요)" >&2
  missing=1
}
if ! gst-inspect-1.0 hailonet >/dev/null 2>&1; then
  echo "WARN: GStreamer hailonet 플러그인 없음" >&2
  missing=1
fi
if [[ "$missing" -ne 0 ]]; then
  echo "Hailo AI Kit / TAPPAS 설치 후 이 스크립트를 다시 실행하세요." >&2
  exit 2
fi

echo "=== HEF 경로 검증 (dry) ==="
python3 - "$HAILO_DIR" <<'PY'
import os, sys
from pathlib import Path
os.environ.setdefault("CRONUSFARM_HAILO_DIR", sys.argv[1])
# resolve_hef만 호출
sys.path.insert(0, os.path.expanduser("~/CronusFarm/scripts"))
import importlib.util
spec = importlib.util.spec_from_file_location(
    "cf_hailo", os.path.expanduser("~/CronusFarm/scripts/cronusfarm_hailo_stream.py")
)
mod = importlib.util.module_from_spec(spec)
# import gi/hailo 없이 hef 파일만 확인
d = Path(sys.argv[1])
hef = d / "best.hef"
assert hef.is_file(), f"missing {hef}"
print(f"OK: HEF file {hef} ({hef.stat().st_size} bytes)")
PY

if [[ ! -f "$SCRIPTS/cronusfarm_hailo_stream.py" ]]; then
  echo "ERROR: $SCRIPTS/cronusfarm_hailo_stream.py 없음" >&2
  exit 1
fi

echo "=== systemd: $SVC_NAME ==="
if [[ ! -f "$SVC_SRC" ]]; then
  echo "ERROR: $SVC_SRC 없음 (git pull)" >&2
  exit 1
fi
UST_SRC="$CRONUS_ROOT/deploy/systemd/cronusfarm-ustreamer.service"
if [[ -f "$UST_SRC" ]]; then
  sudo cp -f "$UST_SRC" /etc/systemd/system/cronusfarm-ustreamer.service
  sudo systemctl enable cronusfarm-ustreamer.service
  sudo systemctl restart cronusfarm-ustreamer.service || true
  sleep 1
fi
sudo cp -f "$SVC_SRC" "/etc/systemd/system/$SVC_NAME"
sudo systemctl daemon-reload
sudo systemctl enable "$SVC_NAME"

# Node-RED drop-in: NR 기동 시 camera-ai 대신 ustreamer+hailo
NR_DROP="$CRONUS_ROOT/deploy/systemd/nodered.service.d/20-cronusfarm-hailo-camera.conf"
if [[ -f "$NR_DROP" ]]; then
  sudo mkdir -p /etc/systemd/system/nodered.service.d
  sudo cp -f "$NR_DROP" /etc/systemd/system/nodered.service.d/20-cronusfarm-hailo-camera.conf
  sudo rm -f /etc/systemd/system/nodered.service.d/20-cronusfarm-camera-ai.conf
  sudo systemctl daemon-reload
fi

# 8081 포트 충돌: CPU YOLO 카메라 서비스 중지 후 Hailo 스트림 기동
if systemctl is-active --quiet cronusfarm-camera-ai.service 2>/dev/null; then
  echo "=== cronusfarm-camera-ai 중지 (8081 → Hailo) ==="
  sudo systemctl stop cronusfarm-camera-ai.service || true
  sudo systemctl disable cronusfarm-camera-ai.service 2>/dev/null || true
fi

sudo systemctl restart "$SVC_NAME"
sleep 2
if systemctl is-active --quiet "$SVC_NAME"; then
  echo "OK: $SVC_NAME active — MJPEG http://$(hostname -I | awk '{print $1}'):8081"
else
  echo "WARN: $SVC_NAME 기동 실패 — journalctl -u $SVC_NAME -n 80" >&2
  exit 3
fi

echo "=== MQTT 토픽: cronusfarm/hailo/count ==="
echo "OK: Hailo AI 설정 완료"
