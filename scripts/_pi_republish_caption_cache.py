#!/usr/bin/env python3
import json
import time
from pathlib import Path

import paho.mqtt.client as mqtt

CACHE = Path.home() / "CronusFarm" / "data" / "crop_caption_cache.json"
TOPIC = "cronusfarm/camera/ai_count"

data = json.loads(CACHE.read_text(encoding="utf-8"))
body = {**data, "timestamp": time.time(), "source": "cache_republish"}
payload = json.dumps(body, ensure_ascii=False)
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
