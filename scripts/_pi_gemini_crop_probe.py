#!/usr/bin/env python3
"""ustreamer 스냅샷으로 Gemini 작물 인식 테스트."""
import os
import sys
from pathlib import Path

ROOT = Path.home() / "CronusFarm"
sys.path.insert(0, str(ROOT / "scripts"))

# nodered-telegram.env 로드
env_path = Path("/etc/cronusfarm/nodered-telegram.env")
if env_path.is_file():
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from cronusfarm_telegram_vision import analyze_gemini  # noqa: E402

IMG = Path("/tmp/ustreamer_snap.jpg")
PROMPT = (
    "이 온실 카메라 사진만 보고 답하세요. JSON 한 줄만 출력:\n"
    '{"crops":[{"name":"한글작물명","count":정수}],"basil_visible":true|false}\n'
    "작물: 토마토, 무화과, 버터헤드, 바질 중 보이는 것만. 바질 잎·화분이 보이면 basil_visible true."
)

if not IMG.is_file():
    print("missing", IMG)
    sys.exit(1)
try:
    text = analyze_gemini(IMG, PROMPT)
    print(text[:800])
except Exception as e:
    print("ERR", e)
    sys.exit(2)
