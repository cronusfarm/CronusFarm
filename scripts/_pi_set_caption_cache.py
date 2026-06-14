#!/usr/bin/env python3
"""캡션 캐시·MQTT 수동 설정 (현장 보정)."""
import json
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt

CACHE = Path.home() / "CronusFarm" / "data" / "crop_caption_cache.json"
TOPIC = "cronusfarm/camera/ai_count"

# 사용: python3 _pi_set_caption_cache.py 바질 1 7
crop = sys.argv[1] if len(sys.argv) > 1 else "바질"
plants = int(sys.argv[2]) if len(sys.argv) > 2 else 1
leaves = int(sys.argv[3]) if len(sys.argv) > 3 else 7

body = {
    "count": leaves,
    "crop_name": crop,
    "crop_count": plants,
    "leaf_count": leaves,
    "caption": f"작물: {crop} | 개수: {plants} | 잎: {leaves}",
}
CACHE.parent.mkdir(parents=True, exist_ok=True)
CACHE.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
payload = json.dumps({**body, "timestamp": time.time(), "source": "manual_set"}, ensure_ascii=False)
try:
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
except AttributeError:
    c = mqtt.Client()
c.connect("127.0.0.1", 1883, 60)
info = c.publish(TOPIC, payload)
if hasattr(info, "wait_for_publish"):
    info.wait_for_publish(timeout=3.0)
c.disconnect()
print(payload)
