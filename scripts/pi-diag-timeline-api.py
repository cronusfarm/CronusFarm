#!/usr/bin/env python3
import json
import time
import urllib.request

hours = 48
u = (
    f"http://127.0.0.1:18766/api/channel/timeline/batch"
    f"?device_id=cronusfarm-01&channels=led_a1,pump_c1,pump_c2&hours={hours}"
)
with urllib.request.urlopen(u, timeout=60) as r:
    b = json.load(r)
for ch, v in (b.get("channels") or {}).items():
    pts = v.get("points") or []
    ones = sum(1 for p in pts if p.get("state") in (1, True))
    t0 = pts[0]["ts_ms"] if pts else None
    t1 = pts[-1]["ts_ms"] if pts else None
    print(
        ch,
        "pts",
        len(pts),
        "ones",
        ones,
        "start",
        time.strftime("%m-%d %H:%M", time.localtime(t0 / 1000)) if t0 else "-",
        "end",
        time.strftime("%m-%d %H:%M", time.localtime(t1 / 1000)) if t1 else "-",
    )
