#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KMA 초단기실황 즉시 조회 → MQTT cronusfarm/kma/snapshot (retain)."""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))
NCST_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"


def load_env() -> dict[str, str]:
    out = dict(os.environ)
    dropin = Path("/etc/systemd/system/nodered.service.d")
    if dropin.is_dir():
        for conf in sorted(dropin.glob("*.conf")):
            text = conf.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                if line.strip().startswith("Environment="):
                    raw = line.strip()[len("Environment=") :].strip().strip('"')
                    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", raw)
                    if m:
                        out[m.group(1)] = m.group(2)
    for p in ("/etc/cronusfarm/nodered-telegram.env",):
        try:
            with open(p, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip().strip("'\"")
        except OSError:
            pass
    return out


def kst_base() -> tuple[str, str]:
    now = datetime.now(KST)
    y, mo, d, hh, mm = now.year, now.month, now.day, now.hour, now.minute
    if mm < 40:
        now = now - timedelta(hours=1)
        y, mo, d, hh = now.year, now.month, now.day, now.hour
    return f"{y:04d}{mo:02d}{d:02d}", f"{hh:02d}00"


def num(v):
    try:
        n = float(v)
        return n if n == n else None
    except (TypeError, ValueError):
        return None


def main() -> int:
    env = load_env()
    key = env.get("CRONUSFARM_KMA_SERVICE_KEY", "").strip()
    nx = int(env.get("CRONUSFARM_KMA_NX", "0") or "0")
    ny = int(env.get("CRONUSFARM_KMA_NY", "0") or "0")
    if not key or not nx or not ny:
        print("ERROR: KMA key or nx/ny missing", file=sys.stderr)
        return 1
    bd, bt = kst_base()
    qs = urllib.parse.urlencode(
        {
            "serviceKey": key,
            "numOfRows": "60",
            "pageNo": "1",
            "dataType": "JSON",
            "base_date": bd,
            "base_time": bt,
            "nx": str(nx),
            "ny": str(ny),
        }
    )
    url = f"{NCST_URL}?{qs}"
    with urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "CronusFarm/kma-refresh"}),
        timeout=30,
    ) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    items = body.get("response", {}).get("body", {}).get("items", {}).get("item", [])
    if not isinstance(items, list):
        print("ERROR: no KMA items", body, file=sys.stderr)
        return 1
    m = {str(it.get("category")): str(it.get("obsrValue", "")) for it in items}
    pty = num(m.get("PTY"))
    rn1 = num(m.get("RN1"))
    snap = {
        "kma_temp": num(m.get("T1H")),
        "kma_humidity": num(m.get("REH")),
        "kma_wind_dir": num(m.get("VEC")),
        "kma_wind_speed": num(m.get("WSD")),
        "kma_pty": pty,
        "kma_precip_type": pty,
        "kma_precip_1h": rn1,
        "base_date": bd,
        "base_time": bt,
        "nx": nx,
        "ny": ny,
        "ts": int(time.time() * 1000),
    }
    print("KMA snap:", json.dumps(snap, ensure_ascii=False))

    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("WARN: paho-mqtt 없음 — snap만 출력", file=sys.stderr)
        return 0

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        client = mqtt.Client()
    client.connect("127.0.0.1", 1883, 60)
    client.publish(
        "cronusfarm/kma/snapshot",
        json.dumps(snap, ensure_ascii=False),
        qos=0,
        retain=True,
    )
    client.disconnect()
    print("OK published cronusfarm/kma/snapshot")
    return 0


if __name__ == "__main__":
    sys.exit(main())
