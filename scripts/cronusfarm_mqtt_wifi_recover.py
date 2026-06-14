#!/usr/bin/env python3
"""
MQTT status 장시간 offline → R4 USB 시리얼 WiFi 프로비저닝(secrets.h 1순위 AP).

cronusfarm_mqtt_watch.py 에서 호출하거나 단독 실행:
  python3 cronusfarm_mqtt_wifi_recover.py
  python3 cronusfarm_mqtt_wifi_recover.py --port /dev/ttyACM2
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CRONUSFARM_ROOT", Path(__file__).resolve().parents[1]))
SECRETS_DEFAULT = ROOT / "arduino" / "CronusFarm" / "secrets.h"
PROVISION_SCRIPT = ROOT / "scripts" / "pi-serial-wifi-provision.py"
FQBN_MARK = "arduino:renesas_uno:unor4wifi"


def _run(cmd: list[str], timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def detect_r4_serial_port(explicit: str = "") -> str | None:
    """UNO R4 WiFi 포트 — arduino-cli FQBN 우선(ACM1 CMSIS-DAP에서도 tele 동작)."""
    if explicit.strip():
        return explicit.strip()
    env = os.environ.get("CRONUSFARM_R4_SERIAL", "").strip()
    if env:
        return env
    r = _run(["arduino-cli", "board", "list"], timeout=20.0)
    if r.returncode == 0:
        for line in r.stdout.splitlines():
            if FQBN_MARK in line:
                parts = line.split()
                if parts:
                    return parts[0]
    by_id = Path("/dev/serial/by-id")
    if by_id.is_dir():
        ranked: list[tuple[int, str]] = []
        for name in sorted(by_id.iterdir()):
            low = name.name.lower()
            if "uno_wifi_r4" not in low:
                continue
            path = str(name)
            prio = 2 if ("if00" in low or "modem" in low) else 1
            ranked.append((prio, path))
        if ranked:
            ranked.sort(key=lambda x: (-x[0], x[1]))
            return ranked[0][1]
    for cand in ("/dev/ttyACM2", "/dev/ttyACM1"):
        if Path(cand).exists():
            return cand
    return None


def parse_secrets_wifi(secrets_path: Path) -> tuple[str, str] | None:
    if not secrets_path.is_file():
        return None
    text = secrets_path.read_text(encoding="utf-8", errors="replace")

    def arr(name: str) -> list[str]:
        m = re.search(rf"{name}\[\]\s*=\s*\{{([^}}]+)\}}", text, re.S)
        if not m:
            return []
        return re.findall(r'"([^"]*)"', m.group(1))

    ssids, passes = arr("WIFI_AP_SSIDS"), arr("WIFI_AP_PASSES")
    if not ssids or not passes:
        return None
    return ssids[0], passes[0]


def provision_wifi(
    port: str,
    secrets_path: Path,
    ssid: str = "",
    psk: str = "",
) -> int:
    if not PROVISION_SCRIPT.is_file():
        print(f"[recover] missing {PROVISION_SCRIPT}", flush=True)
        return 1
    if not ssid or not psk:
        parsed = parse_secrets_wifi(secrets_path)
        if not parsed:
            print(f"[recover] secrets.h 파싱 실패: {secrets_path}", flush=True)
            return 1
        ssid, psk = parsed
    print(f"[recover] WiFi provision port={port} ssid={ssid!r}", flush=True)
    return subprocess.call(
        [
            sys.executable,
            str(PROVISION_SCRIPT),
            "--port",
            port,
            "--ssid",
            ssid,
            "--psk",
            psk,
        ],
    )


def run_auto_recover(
    *,
    secrets_path: Path | None = None,
    port: str = "",
) -> bool:
    """WiFi 프로비저닝 실행. 성공(exit 0)이면 True."""
    secrets_path = secrets_path or Path(
        os.environ.get("CRONUSFARM_SECRETS_PATH", str(SECRETS_DEFAULT))
    )
    serial = detect_r4_serial_port(port)
    if not serial:
        print("[recover] R4 시리얼 포트 없음 — USB 연결 확인", flush=True)
        return False
    rc = provision_wifi(serial, secrets_path)
    if rc == 0:
        print("[recover] OK", flush=True)
        return True
    print(f"[recover] 종료 코드 {rc}", flush=True)
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="R4 MQTT 복구 — 시리얼 WiFi 프로비저닝")
    ap.add_argument("--port", default="", help="R4 시리얼 (기본: 자동)")
    ap.add_argument(
        "--secrets",
        default=str(SECRETS_DEFAULT),
        help="secrets.h 경로",
    )
    args = ap.parse_args()
    ok = run_auto_recover(secrets_path=Path(args.secrets), port=args.port)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
