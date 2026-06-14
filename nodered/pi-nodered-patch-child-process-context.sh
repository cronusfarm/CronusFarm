#!/usr/bin/env bash
# Pi: functionGlobalContext 에 child_process 추가 (Telegram curl 함수용)
set -euo pipefail
S="${HOME}/.node-red/settings.js"
if [[ ! -f "$S" ]]; then
  echo "ERROR: $S 없음" >&2
  exit 1
fi
if grep -q 'child_process:require' "$S" || grep -q "child_process: require" "$S"; then
  echo "OK: child_process 이미 있음"
  exit 0
fi
python3 <<'PY'
from pathlib import Path
p = Path.home() / ".node-red" / "settings.js"
text = p.read_text(encoding="utf-8")
needle = "functionGlobalContext: {"
if needle not in text:
    raise SystemExit("functionGlobalContext 블록 없음")
if "child_process" in text:
    print("OK: already patched")
else:
    text = text.replace(
        needle,
        needle + "\n        child_process: require('child_process'),",
        1,
    )
    p.write_text(text, encoding="utf-8")
    print("OK: child_process 추가")
PY
sudo systemctl restart nodered
echo "nodered 재시작 완료"
