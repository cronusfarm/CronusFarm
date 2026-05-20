#!/usr/bin/env python3
import json
import sys
import urllib.request

url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:18766/api/channel/timeline?device_id=cronusfarm-01&channel=led_a1&hours=24"
d = json.load(urllib.request.urlopen(url, timeout=10))
print("tz", d.get("tz"))
print("anchor", d.get("anchor_ts_ms"))
print("window_end", d.get("window_end_ms"))
print("day_end", d.get("window_day_end_ms"))
print("points", len(d.get("points", [])))
