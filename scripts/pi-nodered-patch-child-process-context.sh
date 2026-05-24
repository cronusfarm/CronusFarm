#!/usr/bin/env bash
# Pi: functionGlobalContext 에 child_process 추가 (Telegram curl 함수용)
set -euo pipefail
S="${HOME}/.node-red/settings.js"
python3 <<'PY'
from pathlib import Path
p = Path.home() / ".node-red" / "settings.js"
text = p.read_text(encoding="utf-8")
old = """    functionGlobalContext: {
        // os:require('os'),
    },"""
new = """    functionGlobalContext: {
        child_process: require('child_process'),
    },"""
if new in text:
    print("OK: 이미 적용됨")
elif old not in text:
    raise SystemExit("functionGlobalContext 기본 블록을 찾지 못함 — 수동 확인 필요")
else:
    text = text.replace(old, new, 1)
    p.write_text(text, encoding="utf-8")
    print("OK: child_process 추가")
PY
sudo systemctl restart nodered
echo "nodered 재시작 완료"
