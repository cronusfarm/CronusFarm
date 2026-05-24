#!/usr/bin/env python3
import json
import sys
import urllib.request

u = "http://127.0.0.1:18766/api/channel/status?device_id=cronusfarm-01"
with urllib.request.urlopen(u, timeout=15) as r:
    d = json.load(r)
for k in ("led_a1", "led_a2", "pump_a1", "fan_a1"):
    print(k, d.get("channels", {}).get(k))
