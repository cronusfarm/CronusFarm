#!/usr/bin/env python3
"""
Pi USB → R4 시리얼(115200) WiFi 프로비저닝.
R4 펌웨어: wifi_set <SSID> <비밀번호> | wifi_clear | wifi_status

사용 (Pi에서, R4 USB 연결):
  python3 ~/CronusFarm/scripts/pi-serial-wifi-provision.py
  python3 ... --port /dev/ttyACM1 --ssid 'Farm_2.4G' --psk '비밀번호'
  python3 ... --clear
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time

BAUD = 115200
FQBN_MARK = "arduino:renesas_uno:unor4wifi"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def detect_r4_port(explicit: str) -> str:
    if explicit:
        return explicit
    env = os.environ.get("CRONUSFARM_R4_SERIAL", "").strip()
    if env:
        return env
    r = _run(["arduino-cli", "board", "list"])
    if r.returncode == 0:
        for line in r.stdout.splitlines():
            if FQBN_MARK in line:
                parts = line.split()
                if parts:
                    return parts[0]
    if os.path.isdir("/dev/serial/by-id"):
        ranked: list[tuple[int, str]] = []
        for name in sorted(os.listdir("/dev/serial/by-id")):
            low = name.lower()
            if "uno_wifi_r4" not in low:
                continue
            path = os.path.join("/dev/serial/by-id", name)
            if "cmsis-dap" in low and "if01" in low:
                continue
            prio = 2 if ("if00" in low or "modem" in low) else (1 if "cmsis-dap" not in low else 0)
            ranked.append((prio, path))
        if ranked:
            ranked.sort(key=lambda x: (-x[0], x[1]))
            return ranked[0][1]
    for cand in ("/dev/ttyACM1", "/dev/ttyACM0"):
        if os.path.exists(cand):
            return cand
    raise SystemExit("R4 시리얼 포트를 찾지 못했습니다. --port 또는 CRONUSFARM_R4_SERIAL 지정")


def read_pi_wifi_from_nmcli() -> tuple[str, str]:
    r = _run(
        [
            "nmcli",
            "-t",
            "-f",
            "ACTIVE,SSID",
            "dev",
            "wifi",
        ]
    )
    ssid = ""
    if r.returncode == 0:
        for line in r.stdout.splitlines():
            if line.startswith("yes:"):
                ssid = line.split(":", 1)[1]
                break
    if not ssid:
        r2 = _run(["/bin/sh", "-c", "iwgetid -r 2>/dev/null || true"])
        if r2.returncode == 0:
            ssid = (r2.stdout or "").strip()

    psk = ""
    r3 = _run(
        [
            "nmcli",
            "-t",
            "-f",
            "NAME,TYPE",
            "connection",
            "show",
            "--active",
        ]
    )
    conn = ""
    if r3.returncode == 0:
        for line in r3.stdout.splitlines():
            if ":802-11-wireless" in line or line.endswith(":wifi"):
                conn = line.split(":")[0]
                break
    if conn:
        r4 = _run(
            [
                "nmcli",
                "-s",
                "-g",
                "802-11-wireless-security.psk",
                "connection",
                "show",
                conn,
            ]
        )
        if r4.returncode == 0:
            psk = (r4.stdout or "").strip()
    return ssid, psk


def open_serial(port: str):
    """DTR/RTS 로 보드를 리셋하지 않음 — open 직후 wifi_set 이 무시되는 문제 방지."""
    try:
        import serial
    except ImportError as e:
        raise SystemExit(
            "pyserial 없음: pip3 install pyserial --break-system-packages"
        ) from e
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = BAUD
    ser.timeout = 0.5
    ser.dtr = False
    ser.rts = False
    ser.open()
    try:
        ser.setDTR(False)
        ser.setRTS(False)
    except Exception:
        pass
    time.sleep(0.15)
    return ser


def wait_boot_banner(ser, timeout_s: float = 90.0) -> bool:
    """펌웨어 'CronusFarm setup...' 또는 WiFi/MQTT 로그가 나올 때까지 대기."""
    markers = (
        "CronusFarm setup",
        "BOOT self-test",
        "WiFi 연결됨",
        "WiFi 재연결됨",
        "MQTT 연결",
        "OK wifi_status",
    )
    deadline = time.time() + timeout_s
    buf: list[str] = []
    while time.time() < deadline:
        raw = ser.readline()
        if not raw:
            time.sleep(0.05)
            continue
        text = raw.decode("utf-8", errors="replace").strip()
        if not text:
            continue
        buf.append(text)
        print(text)
        if any(m in text for m in markers):
            return True
    if not buf:
        print(
            f"[provision] 부팅 로그 없음 ({int(timeout_s)}s) — USB·포트·펌웨어 업로드 확인",
            file=sys.stderr,
        )
    return False


def drain(ser, seconds: float = 0.4) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        n = ser.in_waiting
        if n:
            ser.read(n)
        else:
            time.sleep(0.05)


def send_command(ser, cmd: str, wait_s: float = 45.0) -> list[str]:
    line = cmd.strip() + "\n"
    ser.write(line.encode("utf-8", errors="replace"))
    ser.flush()
    out: list[str] = []
    deadline = time.time() + wait_s
    while time.time() < deadline:
        raw = ser.readline()
        if not raw:
            time.sleep(0.05)
            continue
        text = raw.decode("utf-8", errors="replace").strip()
        if text:
            out.append(text)
            print(text)
        # disconnected 로 조기 종료하면 wifi_set 직후(아직 연결 전)에 멈춤
        if "ERR wifi_set" in text or "OK wifi_clear" in text:
            break
        if "OK wifi_status connected" in text or "WiFi 재연결됨" in text:
            break
        if "WiFi 연결됨" in text and "0.0.0.0" not in text:
            break
        if cmd.strip() == "wifi_status" and "OK wifi_status" in text:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Pi USB → R4 WiFi 시리얼 프로비저닝")
    ap.add_argument("--port", default="", help="R4 시리얼 (기본: 자동 탐지)")
    ap.add_argument("--ssid", default="", help="SSID (기본: Pi 현재 WiFi)")
    ap.add_argument("--psk", default="", help="비밀번호 (기본: nmcli)")
    ap.add_argument("--clear", action="store_true", help="EEPROM WiFi 삭제만")
    ap.add_argument("--status", action="store_true", help="wifi_status 만 조회")
    args = ap.parse_args()

    port = detect_r4_port(args.port)
    print(f"[provision] port={port}")

    ser = open_serial(port)
    boot_wait = float(os.environ.get("CRONUSFARM_WIFI_BOOT_WAIT_SEC", "90") or 90)
    if not args.status and not args.clear:
        print(f"[provision] R4 부팅 로그 대기 (최대 {int(boot_wait)}s, DTR 리셋 없음)...")
        wait_boot_banner(ser, timeout_s=boot_wait)
    else:
        time.sleep(0.6)
        drain(ser, 0.5)

    if args.clear:
        send_command(ser, "wifi_clear", wait_s=5.0)
        ser.close()
        return 0

    if args.status:
        send_command(ser, "wifi_status", wait_s=3.0)
        ser.close()
        return 0

    ssid = args.ssid.strip() or os.environ.get("CRONUSFARM_WIFI_SSID", "").strip()
    psk = args.psk or os.environ.get("CRONUSFARM_WIFI_PSK", "").strip()
    if not ssid or not psk:
        nssid, npsk = read_pi_wifi_from_nmcli()
        ssid = ssid or nssid
        psk = psk or npsk
    if not ssid or not psk:
        print(
            "[error] SSID/비밀번호 없음. --ssid/--psk 또는 nmcli(sudo) 확인",
            file=sys.stderr,
        )
        ser.close()
        return 1

    if re.search(r"[\r\n]", ssid) or re.search(r"[\r\n]", psk):
        print("[error] SSID/비밀번호에 줄바꿈 불가", file=sys.stderr)
        ser.close()
        return 1

    cmd = f"wifi_set {ssid} {psk}"
    print(f"[provision] send: wifi_set {ssid} ****")
    wait_s = float(os.environ.get("CRONUSFARM_WIFI_PROVISION_WAIT_SEC", "45") or 45)
    lines = send_command(ser, cmd, wait_s=wait_s)
    ser.close()

    ok = any(
        "OK wifi_status connected" in ln
        or "WiFi 재연결됨" in ln
        or ("WiFi 연결됨" in ln and "0.0.0.0" not in ln)
        or "MQTT 연결" in ln
        for ln in lines
    )
    if ok:
        print("[ok] R4 WiFi 프로비저닝 성공")
        return 0
    if not lines:
        print(
            "[warn] 시리얼 응답 0줄 — pi-reset 직후 90초 대기, mqtt-watch 중지, "
            "DTR 무리셋 펌웨어·포트(/dev/ttyACM2) 확인",
            file=sys.stderr,
        )
    else:
        print("[warn] WiFi 연결 확인 메시지 없음 — 시리얼 로그·비밀번호 확인", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
