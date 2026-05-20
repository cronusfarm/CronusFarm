#!/usr/bin/env bash
# x86_64 Linux + Hailo Dataflow Compiler(hailo CLI) 필요. Raspberry Pi(ARM)에서는 전체 ONNX→HEF 컴파일 불가(벤더 제약).
# 사용 전: Hailo 가이드대로 venv 활성화 후 이 스크립트 실행.
#
# 환경변수(선택):
#   HAILO_HW_ARCH   기본 hailo8l (Pi AI Kit / Hailo-8L)
#   CRONUSFARM_HAILO_DIR  기본: 저장소 CronusFarm/Hailo (이 스크립트 기준 상위/../Hailo)

set -euo pipefail

ARCH="${HAILO_HW_ARCH:-hailo8l}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
HAILO_DIR="${CRONUSFARM_HAILO_DIR:-$REPO_ROOT/Hailo}"

if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "ERROR: ONNX→HEF 전체 파이프라인은 x86_64 Linux 에서만 실행하세요 (현재: $(uname -m))." >&2
  echo "  Windows: WSL2 Ubuntu(x86_64) + Hailo DFC 설치 후 이 스크립트를 다시 실행합니다." >&2
  exit 1
fi

if ! command -v hailo >/dev/null 2>&1; then
  echo "ERROR: hailo CLI 없음. Hailo AI Software Suite(Dataflow Compiler) 설치 및 venv 활성화 후 다시 실행하세요." >&2
  exit 1
fi

cd "$HAILO_DIR"
if [[ ! -f best.onnx ]]; then
  echo "ERROR: $HAILO_DIR/best.onnx 없음. Windows에서 cronusfarm-hailo-prepare-best.ps1 로 복사하세요." >&2
  exit 1
fi

echo "[hailo-dfc] dir=$HAILO_DIR arch=$ARCH"

echo "[1/3] hailo parser onnx …"
set +e
hailo parser onnx best.onnx --hw-arch "$ARCH" 2>&1 | tee /tmp/cf-hailo-parser.log
RC=${PIPESTATUS[0]}
set -e
if [[ "$RC" != "0" ]]; then
  echo "ERROR: parser 실패(rc=$RC). DFC 버전에 따라 인자가 다를 수 있습니다: hailo parser onnx --help" >&2
  exit "$RC"
fi

HAR="$(find . -maxdepth 1 -type f -name '*.har' -printf '%T@\t%p\n' 2>/dev/null | sort -nr | head -1 | cut -f2- || true)"
if [[ -z "$HAR" ]]; then
  echo "ERROR: .har 산출물을 찾지 못했습니다. /tmp/cf-hailo-parser.log 를 확인하세요." >&2
  exit 1
fi
echo "[hailo-dfc] HAR=$HAR"

HAR_BASE="$(basename "$HAR" .har)"
ALLS=""
if [[ -f "${HAR_BASE}.alls" ]]; then
  ALLS="${HAR_BASE}.alls"
elif [[ -f yolov8_crops.alls ]]; then
  ALLS="yolov8_crops.alls"
fi
if [[ -n "$ALLS" ]]; then
  echo "[hailo-dfc] model-script=$ALLS (NMS·sigmoid — Pi 오버레이용)"
else
  echo "WARN: .alls 없음 — HEF에 nms_postprocess가 없으면 hailooverlay 박스가 나오지 않습니다." >&2
fi

echo "[2/3] hailo optimize … (임의 캘리브레이션 — 운영 정확도는 캘리브 이미지 세트로 다시 하세요)"
set +e
OPT_ARGS=("$HAR" --hw-arch "$ARCH")
if [[ -n "$ALLS" ]]; then
  OPT_ARGS+=(--model-script "$ALLS")
fi
if hailo optimize --help 2>&1 | grep -q use-random-calib-set; then
  hailo optimize "${OPT_ARGS[@]}" --use-random-calib-set 2>&1 | tee /tmp/cf-hailo-opt.log
else
  hailo optimize "${OPT_ARGS[@]}" 2>&1 | tee /tmp/cf-hailo-opt.log
fi
RC=${PIPESTATUS[0]}
set -e
if [[ "$RC" != "0" ]]; then
  echo "ERROR: optimize 실패(rc=$RC). hailo optimize --help 및 모델 스크립트·캘리브 경로를 확인하세요." >&2
  exit "$RC"
fi

HAR_OPT="$(find . -maxdepth 1 -type f -name '*.har' -printf '%T@\t%p\n' 2>/dev/null | sort -nr | head -1 | cut -f2- || true)"
if [[ -z "$HAR_OPT" ]]; then
  echo "ERROR: 최적화 후 .har 를 찾지 못했습니다." >&2
  exit 1
fi
echo "[hailo-dfc] optimized HAR→ $HAR_OPT"

echo "[3/3] hailo compiler …"
set +e
hailo compiler "$HAR_OPT" 2>&1 | tee /tmp/cf-hailo-comp.log
RC=${PIPESTATUS[0]}
set -e
if [[ "$RC" != "0" ]]; then
  echo "ERROR: compiler 실패(rc=$RC). hailo compiler --help 로 인자 확인." >&2
  exit "$RC"
fi

HEF="$(find . -maxdepth 1 -type f -name '*.hef' -printf '%T@\t%p\n' 2>/dev/null | sort -nr | head -1 | cut -f2- || true)"
if [[ -z "$HEF" ]]; then
  echo "ERROR: .hef 산출물을 찾지 못했습니다." >&2
  exit 1
fi
if [[ "$(basename "$HEF")" != "best.hef" ]]; then
  cp -f "$HEF" best.hef
  echo "[hailo-dfc] $HEF → best.hef 로 복사"
else
  echo "[hailo-dfc] $HEF 생성됨"
fi

echo "OK: $HAILO_DIR/best.hef 준비됨. Windows에서 deploy-cronusfarm-pi.ps1 로 Pi 에 동기화하세요."
