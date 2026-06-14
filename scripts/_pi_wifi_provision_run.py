#!/usr/bin/env python3
import re
import subprocess
import sys

secrets = "/home/dooly/CronusFarm/arduino/CronusFarm/secrets.h"
port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM1"
prov = "/home/dooly/CronusFarm/scripts/pi-serial-wifi-provision.py"
text = open(secrets, encoding="utf-8", errors="replace").read()


def arr(name: str) -> list[str]:
    m = re.search(rf"{name}\[\]\s*=\s*\{{([^}}]+)\}}", text, re.S)
    if not m:
        return []
    return re.findall(r'"([^"]*)"', m.group(1))


ssids, passes = arr("WIFI_AP_SSIDS"), arr("WIFI_AP_PASSES")
if not ssids or not passes:
    raise SystemExit("secrets.h 파싱 실패")
ssid, psk = ssids[0], passes[0]
print(f"[run] ssid={ssid!r} port={port}")
raise SystemExit(
    subprocess.call(["python3", prov, "--port", port, "--ssid", ssid, "--psk", psk])
)
