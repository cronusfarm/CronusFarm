#!/usr/bin/env python3
import json
import urllib.request

for path in (
    "http://127.0.0.1:18766/api/channel/status?device_id=cronusfarm-01",
    "http://127.0.0.1:1882/farm/cronusfarm-sqlite/api/channel/status?device_id=cronusfarm-01",
):
    try:
        with urllib.request.urlopen(path, timeout=10) as r:
            d = json.loads(r.read())
        print("===", path)
        ch = d.get("channels") or d
        if isinstance(ch, dict):
            for k in sorted(ch.keys()):
                v = ch[k] if isinstance(ch[k], dict) else {}
                print(
                    f"  {k}: state={v.get('state')} auto={v.get('auto_mode')} mode={v.get('display_mode')}"
                )
    except Exception as e:
        print("===", path, "ERR", e)
