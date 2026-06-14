#!/usr/bin/env python3
import os
import sys
from pathlib import Path

ROOT = Path.home() / "CronusFarm"
sys.path.insert(0, str(ROOT / "scripts"))

env_path = Path("/etc/cronusfarm/nodered-telegram.env")
if env_path.is_file():
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

import cv2
from cronusfarm_crop_caption import (
    GEMINI_CROP_PROMPT,
    analysis_from_gemini_crop_json,
)
from cronusfarm_telegram_vision import analyze_gemini

URL = "http://127.0.0.1:8080/stream"
OUT = Path("/tmp/cf_hailo_gemini_cap.jpg")

cap = cv2.VideoCapture(URL)
ok, frame = cap.read()
cap.release()
if not ok:
    print("no frame")
    sys.exit(1)

# letterbox same as hailo_stream
h, w = frame.shape[:2]
size = 640
scale = min(size / h, size / w)
nh, nw = int(round(h * scale)), int(round(w * scale))
resized = cv2.resize(frame, (nw, nh))
bgr = __import__("numpy").zeros((size, size, 3), dtype=frame.dtype)
top, left = (size - nh) // 2, (size - nw) // 2
bgr[top : top + nh, left : left + nw] = resized

cv2.imwrite(str(OUT), bgr)
text = analyze_gemini(OUT, GEMINI_CROP_PROMPT)
print("raw:", text[:200])
analysis = analysis_from_gemini_crop_json(text)
print("analysis:", analysis)
