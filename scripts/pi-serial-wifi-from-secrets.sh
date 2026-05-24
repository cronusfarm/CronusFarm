#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRETS="${CRONUSFARM_SECRETS:-$ROOT/arduino/CronusFarm/secrets.h}"
PORT="${CRONUSFARM_R4_SERIAL:-/dev/ttyACM1}"
export CRONUSFARM_ROOT="$ROOT"
exec python3 - "$SECRETS" "$PORT" "$ROOT/scripts/pi-serial-wifi-provision.py" <<'PY'
import os, re, subprocess, sys
path, port, prov = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(path, encoding="utf-8", errors="replace").read()

def arr(name):
    m = re.search(rf"{name}\[\]\s*=\s*\{{([^}}]+)\}}", text, re.S)
    if not m:
        return []
    return re.findall(r'"([^"]*)"', m.group(1))

ssids, passes = arr("WIFI_AP_SSIDS"), arr("WIFI_AP_PASSES")
if not ssids or not passes:
    raise SystemExit("secrets.h SSID/비밀번호 파싱 실패")
ssid, psk = ssids[0], passes[0]
print(f"[wifi-from-secrets] ssid={ssid!r} port={port}")
raise SystemExit(subprocess.call(["python3", prov, "--port", port, "--ssid", ssid, "--psk", psk]))
PY
