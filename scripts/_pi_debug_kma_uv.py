#!/usr/bin/env python3
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))


def load_env():
    import re

    out = dict(os.environ)
    dropin = Path("/etc/systemd/system/nodered.service.d")
    if dropin.is_dir():
        for conf in sorted(dropin.glob("*.conf")):
            for line in conf.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.strip().startswith("Environment="):
                    raw = line.strip()[len("Environment=") :].strip().strip('"')
                    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", raw)
                    if m:
                        out[m.group(1)] = m.group(2)
    for p in ("/etc/cronusfarm/nodered-telegram.env",):
        try:
            for line in Path(p).read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip().strip("'\"")
        except OSError:
            pass
    return out


e = load_env()
key = e.get("CRONUSFARM_KMA_SERVICE_KEY", "")
now = datetime.now(KST)
ymdh = now.strftime("%Y%m%d%H")
print("ymdh", ymdh, "key_len", len(key))
for area in ("4117300000", "4111100000", "1100000000"):
    q = urllib.parse.urlencode(
        {
            "serviceKey": key,
            "pageNo": "1",
            "numOfRows": "3",
            "dataType": "JSON",
            "areaNo": area,
            "time": ymdh,
        }
    )
    url = f"https://apis.data.go.kr/1360000/LivingWthrIdxServiceV4/getUVIdxV4?{q}"
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "CronusFarm"}),
            timeout=15,
        )
        b = json.loads(r.read().decode())
        h = b.get("response", {}).get("header", {})
        items = b.get("response", {}).get("body", {}).get("items")
        print(area, "rc", h.get("resultCode"), h.get("resultMsg"), "items", str(items)[:180])
    except Exception as ex:
        print(area, "ERR", ex)
