#!/usr/bin/env python3
"""
R4 USB 시리얼 ↔ Pi SQLite 브리지 (MQTT 없이 tele/cmd).

- R4 → Pi: tele 줄(S:|로 시작), CF_STATUS online|offline
- Pi → R4: CMD rtc_local=… / time_local=… (Pi KST 14자리 → R4 소프트 시계) + key=value
- 업로드 중: /run/cronusfarm/r4-upload.lock 있으면 포트 닫고 대기

환경:
  CRONUSFARM_R4_SERIAL          /dev/ttyACM2 또는 by-id
  CRONUSFARM_SQLITE_BRIDGE_URL  http://127.0.0.1:18766
  CRONUSFARM_R4_SERIAL_API      http://127.0.0.1:18767 (cmd 수신)
  CRONUSFARM_DEVICE_ID          cronusfarm-01
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(os.environ.get("CRONUSFARM_ROOT", Path(__file__).resolve().parents[1]))
LOCK_FILE = Path(os.environ.get("CRONUSFARM_R4_UPLOAD_LOCK", "/run/cronusfarm/r4-upload.lock"))
BRIDGE_URL = os.environ.get("CRONUSFARM_SQLITE_BRIDGE_URL", "http://127.0.0.1:18766").rstrip("/")
DEVICE_ID = os.environ.get("CRONUSFARM_DEVICE_ID", "cronusfarm-01").strip()
API_PORT = int(os.environ.get("CRONUSFARM_R4_SERIAL_API_PORT", "18767") or 18767)
INGEST_REPUBLISH = os.environ.get("CRONUSFARM_INGEST_REPUBLISH_MQTT", "0").strip().lower() in (
    "1",
    "true",
    "yes",
)
TELE_TOPIC = f"cronusfarm/{DEVICE_ID}/tele"
STATUS_TOPIC = f"cronusfarm/{DEVICE_ID}/status"
# tele N초 이상 없으면 rtc_local push 중단 → R4가 Pi offline·builtin 전환
TIME_PUSH_PAUSE_TELE_STALE_SEC = float(
    os.environ.get("CRONUSFARM_TIME_PUSH_PAUSE_TELE_STALE_SEC", "600") or 600
)
TELE_WATCH_SEC = float(os.environ.get("CRONUSFARM_SERIAL_TELE_WATCH_SEC", "420") or 420)
RESET_COOLDOWN_SEC = float(
    os.environ.get("CRONUSFARM_SERIAL_RESET_COOLDOWN_SEC", "300") or 300
)

_serial_lock = threading.Lock()
_ser = None
_last_status_online_ms = 0.0
_last_tele_rx_ms = 0.0
_last_time_push_ms = 0.0
_last_time_payload = ""
_last_watch_action_ms = 0.0


def _kst_rtc_yyyymmddhhmmss() -> str:
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d%H%M%S")
    except Exception:
        pass
    try:
        out = subprocess.check_output(["date", "+%Y%m%d%H%M%S"], text=True, timeout=5)
        return out.strip()
    except Exception:
        return time.strftime("%Y%m%d%H%M%S")


def _push_time_local() -> bool:
    """Pi KST → R4 소프트 시계 (USB CMD rtc_local). Pi가 R4보다 늦게 부팅해도 주기·TIME?로 재시도."""
    global _last_time_push_ms, _last_time_payload
    if (
        _last_tele_rx_ms > 0
        and (time.time() - _last_tele_rx_ms) >= TIME_PUSH_PAUSE_TELE_STALE_SEC
    ):
        return False
    payload = f"rtc_local={_kst_rtc_yyyymmddhhmmss()}"
    now = time.time()
    if payload == _last_time_payload and (now - _last_time_push_ms) < 12.0:
        return True
    ok = _write_cmd_line(payload)
    if ok:
        _last_time_push_ms = now
        _last_time_payload = payload
        print(f"[serial] time-push ok {payload}", flush=True)
    return ok


def _time_pusher_loop() -> None:
    """R4·R3가 Pi보다 먼저 켜지는 경우: 부팅 후 5분은 20초, 이후 60초마다 시각 전송."""
    boot_phase_until = time.time() + 300.0
    while True:
        interval = 20.0 if time.time() < boot_phase_until else 60.0
        time.sleep(interval)
        if LOCK_FILE.is_file():
            continue
        with _serial_lock:
            if _ser is None or not getattr(_ser, "is_open", False):
                continue
        _push_time_local()


def _tele_watchdog_loop() -> None:
    """tele 장시간 없으면 reboot cmd → soft reset → upload (물리 리셋 불필요)."""
    global _last_watch_action_ms
    reset_sh = ROOT / "scripts" / "pi-reset-r4.sh"
    upload_sh = ROOT / "scripts" / "pi-upload-r4.sh"
    while True:
        time.sleep(45)
        if LOCK_FILE.is_file():
            continue
        if _last_tele_rx_ms <= 0:
            continue
        gap = time.time() - _last_tele_rx_ms
        if gap < TELE_WATCH_SEC:
            continue
        now = time.time()
        if now - _last_watch_action_ms < RESET_COOLDOWN_SEC:
            continue
        _last_watch_action_ms = now
        print(f"[serial-watch] tele silent {gap:.0f}s — reboot=1", flush=True)
        _write_cmd_line("reboot=1")
        time.sleep(22)
        if time.time() - _last_tele_rx_ms < 60:
            print("[serial-watch] reboot cmd OK", flush=True)
            continue
        if reset_sh.is_file():
            print("[serial-watch] reboot 무효 — pi-reset-r4.sh", flush=True)
            with _serial_lock:
                _close_serial_locked()
            subprocess.run(
                ["bash", str(reset_sh)],
                cwd=str(ROOT),
                timeout=150,
                check=False,
            )
            time.sleep(35)
        if time.time() - _last_tele_rx_ms < 90:
            print("[serial-watch] soft reset OK", flush=True)
            continue
        if upload_sh.is_file():
            print("[serial-watch] soft reset 실패 — pi-upload-r4.sh", flush=True)
            env = os.environ.copy()
            env.setdefault("HOME", "/home/dooly")
            subprocess.run(
                ["bash", str(upload_sh)],
                cwd=str(ROOT),
                timeout=420,
                check=False,
                env=env,
            )
            time.sleep(90)


def _detect_port() -> str:
    explicit = os.environ.get("CRONUSFARM_R4_SERIAL", "").strip()
    if explicit:
        return explicit

    def _is_r3_uno_port(path: str) -> bool:
        """R3 패널(arduino:avr:uno) 포트 — R4와 혼동 방지."""
        try:
            out = subprocess.check_output(
                ["arduino-cli", "board", "list"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=15,
            )
            for line in out.splitlines():
                if "arduino:avr:uno" in line and path in line:
                    return True
        except Exception:
            pass
        low = path.lower()
        if "arduino_uno_" in low and "wifi_r4" not in low:
            return True
        return False

    try:
        from cronusfarm_mqtt_wifi_recover import detect_r4_serial_port

        p = detect_r4_serial_port("")
        if p and Path(p).exists() and not _is_r3_uno_port(p):
            return p
    except Exception:
        pass

    by_id = Path("/dev/serial/by-id")
    if by_id.is_dir():
        for p in sorted(by_id.glob("*UNO_WiFi_R4*")):
            return str(p)

    for cand in ("/dev/ttyACM2", "/dev/ttyACM1"):
        if Path(cand).exists() and not _is_r3_uno_port(cand):
            return cand
    raise SystemExit("R4 시리얼 포트 없음 — CRONUSFARM_R4_SERIAL 지정")


def open_serial_no_reset(port: str):
    import serial

    # CMSIS-DAP(ACM1)에서 DTR/RTS를 끄면 R4 tele 출력이 멈추는 경우가 있음.
    ser = serial.Serial(port, 115200, timeout=0.25)
    time.sleep(0.15)
    return ser


def _bridge_post(path: str, body: dict) -> bool:
    url = f"{BRIDGE_URL}{path}"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        print(f"[serial] bridge POST {path} fail: {e}", flush=True)
        return False


def _ingest_tele(raw: str) -> None:
    _bridge_post(
        "/ingest/tele",
        {
            "device_id": DEVICE_ID,
            "topic": TELE_TOPIC,
            "raw": raw,
            "ts_ms": int(time.time() * 1000),
            "via": "usb-serial",
        },
    )


def _ingest_status(payload: str) -> None:
    _bridge_post(
        "/ingest/status",
        {
            "device_id": DEVICE_ID,
            "topic": STATUS_TOPIC,
            "payload": payload,
            "ts_ms": int(time.time() * 1000),
            "via": "usb-serial",
        },
    )


def _close_serial_locked() -> None:
    global _ser
    if _ser is None:
        return
    try:
        if getattr(_ser, "is_open", False):
            _ser.close()
    except OSError:
        pass
    _ser = None


def _write_cmd_line(payload: str) -> bool:
    global _ser
    body = payload.strip()
    if not body.upper().startswith("CMD "):
        body = "CMD " + body
    line = body + "\r\n"
    tele_lines: list[str] = []
    wrote = False
    with _serial_lock:
        if _ser is None or not getattr(_ser, "is_open", False):
            return False
        try:
            ser = _ser
            ser.write(line.encode("utf-8", errors="replace"))
            try:
                ser.flush()
            except OSError as e:
                print(f"[serial] cmd flush fail: {e}", flush=True)
                _close_serial_locked()
                return False
            wrote = True
            deadline = time.time() + 1.2
            while time.time() < deadline:
                waiting = getattr(ser, "in_waiting", 0) or 0
                if waiting:
                    try:
                        rx = ser.readline().decode("utf-8", errors="replace").strip()
                    except OSError as e:
                        print(f"[serial] cmd-rx fail: {e}", flush=True)
                        _close_serial_locked()
                        return wrote
                    if rx:
                        print(f"[serial] cmd-rx: {rx}", flush=True)
                        if rx.startswith("S:") or rx.startswith("S|"):
                            tele_lines.append(rx)
                        elif "OK cmd" in rx or "CMD 수신" in rx:
                            break
                else:
                    time.sleep(0.05)
            print(f"[serial] cmd-tx: {body}", flush=True)
        except OSError as e:
            print(f"[serial] cmd write fail: {e}", flush=True)
            _close_serial_locked()
            return False
    for tl in tele_lines:
        _handle_rx_line(tl)
    return wrote


def _handle_rx_line(text: str) -> None:
    text = text.strip()
    if not text:
        return
    if text.startswith("S:") or text.startswith("S|"):
        # USB primary 구성에서는 MQTT status retain이 stale offline으로 남기 쉬움(LWT/구형 status).
        # tele을 받는 순간은 링크가 살아있다는 의미이므로 status=online을 함께 기록/재발행합니다.
        global _last_status_online_ms, _last_tele_rx_ms
        now = time.time()
        _last_tele_rx_ms = now
        if now - _last_status_online_ms >= 30.0:
            _ingest_status("online")
            _last_status_online_ms = now
        _ingest_tele(text)
        return
    if text.strip() == "TIME?":
        _push_time_local()
        return
    if text.startswith("CF_STATUS "):
        st = text.split(None, 1)[-1].strip().lower()
        # R4가 보고하는 CF_STATUS는 "MQTT 연결상태"일 수 있어 USB primary에서는 오탐(offline)을 유발합니다.
        # offline은 무시하고, online만 반영합니다. (offline은 tele stale로 판단)
        if st == "online":
            _ingest_status("online")
        return


def _reader_loop(port: str) -> None:
    global _ser
    while True:
        if LOCK_FILE.is_file():
            with _serial_lock:
                if _ser and getattr(_ser, "is_open", False):
                    try:
                        _ser.close()
                    except OSError:
                        pass
                    _ser = None
            time.sleep(1.0)
            continue
        need_open = False
        with _serial_lock:
            need_open = _ser is None or not getattr(_ser, "is_open", False)
        if need_open:
            try:
                new_ser = open_serial_no_reset(port)
            except OSError as e:
                print(f"[serial] open fail: {e}", flush=True)
                time.sleep(3.0)
                continue
            with _serial_lock:
                _ser = new_ser
            print(f"[serial] open {port}", flush=True)
            for i in range(12):
                if _push_time_local():
                    if i >= 2:
                        break
                time.sleep(1.0)
        with _serial_lock:
            ser = _ser
            if ser is None or not getattr(ser, "is_open", False):
                continue
        try:
            raw = ser.readline()
        except OSError as e:
            print(f"[serial] read fail: {e}", flush=True)
            with _serial_lock:
                _close_serial_locked()
            time.sleep(2.0)
            continue
        if not raw:
            continue
        line = raw.decode("utf-8", errors="replace").strip()
        if line:
            print(line, flush=True)
            _handle_rx_line(line)


class CmdHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print(f"[serial-api] {self.address_string()} {fmt % args}", flush=True)

    def do_POST(self) -> None:
        if self.path not in ("/r4/cmd", "/cmd"):
            self.send_error(404)
            return
        n = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(n) if n > 0 else b"{}"
        try:
            data = json.loads(body.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            data = {"payload": body.decode("utf-8", errors="replace")}
        payload = str(data.get("payload") or "").strip()
        if not payload:
            self.send_error(400, "payload required")
            return
        prefix = "CMD " if not payload.startswith("CMD ") else ""
        try:
            ok = _write_cmd_line(prefix + payload if prefix else payload)
        except OSError as e:
            print(f"[serial-api] cmd unexpected: {e}", flush=True)
            ok = False
        out = {"ok": ok, "device_id": DEVICE_ID, "via": "usb-serial"}
        raw = json.dumps(out, ensure_ascii=False).encode("utf-8")
        self.send_response(200 if ok else 503)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path in ("/health", "/"):
            raw = json.dumps({"ok": True, "device_id": DEVICE_ID}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        self.send_error(404)


def main() -> None:
    port = _detect_port()
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    print(
        f"[serial] start port={port} bridge={BRIDGE_URL} api=:{API_PORT} "
        f"republish_mqtt={INGEST_REPUBLISH}",
        flush=True,
    )
    threading.Thread(target=_reader_loop, args=(port,), daemon=True).start()
    threading.Thread(target=_time_pusher_loop, daemon=True).start()
    threading.Thread(target=_tele_watchdog_loop, daemon=True).start()
    httpd = ThreadingHTTPServer(("127.0.0.1", API_PORT), CmdHandler)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
