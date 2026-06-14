#!/usr/bin/env python3
"""즉시 작물 캡션 MQTT 발행 + 캐시 저장 (Gemini 1회)."""
import json
import os
import sys
import time
from pathlib import Path

import cv2

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

from cronusfarm_crop_caption import (  # noqa: E402
    analysis_from_gemini_crop_json,
    gemini_crop_prompt,
)
from cronusfarm_hailo_stream import (  # noqa: E402
    _CAPTION_CACHE_PATH,
    _gemini_analyze_crop,
    _letterbox_bgr,
    _save_caption_cache,
)

URL = os.environ.get("CRONUSFARM_HAILO_USTREAMER_URL", "http://127.0.0.1:8080/stream")
TOPIC = os.environ.get("CRONUSFARM_AI_MQTT_TOPIC", "cronusfarm/camera/ai_count")
TMP = Path("/tmp/cf_push_crop_cap.jpg")


def main() -> None:
    cap = cv2.VideoCapture(URL)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        print("no frame")
        sys.exit(1)
    bgr = _letterbox_bgr(frame, 640)
    cv2.imwrite(str(TMP), bgr)
    print("gemini 요청…", flush=True)
    os.environ.setdefault("CRONUSFARM_CAPTION_CROP_HINT", "바질")
    text = _gemini_analyze_crop(TMP)
    print("raw:", text[:160])
    analysis = analysis_from_gemini_crop_json(text)
    if not analysis or int(analysis.get("count") or 0) <= 0:
        print("분석 실패 또는 작물 없음", analysis)
        sys.exit(2)
    _save_caption_cache(analysis)
    body = {
        "count": analysis.get("count"),
        "caption": analysis.get("caption"),
        "crop_name": analysis.get("crop_name"),
        "crop_count": analysis.get("crop_count"),
        "leaf_count": analysis.get("leaf_count"),
        "timestamp": time.time(),
        "source": "manual_push",
    }
    payload = json.dumps(body, ensure_ascii=False)
    import paho.mqtt.client as mqtt

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        client = mqtt.Client()
    client.connect("127.0.0.1", 1883, 60)
    client.publish(TOPIC, payload)
    client.disconnect()
    print("MQTT OK:", payload)
    print("cache:", _CAPTION_CACHE_PATH)


if __name__ == "__main__":
    main()
