#!/usr/bin/env python3
"""
R4 USB 시리얼 ↔ Pi SQLite 브리지 (MQTT 없이 tele/cmd).

- R4 → Pi: tele 줄(S:|로 시작), CF_STATUS online|offline
- Pi → R4: CMD rtc_local=… / key=value (줄 단위)
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

_serial_lock = threading.Lock()
_ser = None


def _detect_port() -> str:
    explicit = os.environ.get("CRONUSFARM_R4_SERIAL", "").strip()
    if explicit:
        return explicit
    try:
        from cronusfarm_mqtt_wifi_recover import detect_r4_serial_port

        p = detect_r4_serial_port("")
        if p:
            return p
    except Exception:
        pass
    for cand in ("/dev/ttyACM1", "/dev/ttyACM0", "/dev/ttyACM2"):
        if Path(cand).exists():
            return cand
    raise SystemExit("R4 시리얼 포트 없음 — CRONUSFARM_R4_SERIAL 지정")


def open_serial_no_reset(port: str):
    import serial

    ser = serial.Serial()
    ser.port = port
    ser.baudrate = 115200
    ser.timeout = 0.25
    ser.dtr = False
    ser.rts = False
    ser.open()
    try:
        ser.setDTR(False)
        ser.setRTS(False)
    except Exception:
        pass
    time.sleep(0.1)
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
        with urllib.request.urlopen(req, timeout=8) as resp:
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
        },
    )


def _write_cmd_line(payload: str) -> bool:
    global _ser
    body = payload.strip()
    if not body.upper().startswith("CMD "):
        body = "CMD " + body
    line = body + "\r\n"
    with _serial_lock:
        if _ser is None or not getattr(_ser, "is_open", False):
            return False
        try:
            ser = _ser
            ser.reset_input_buffer()
            ser.write(line.encode("utf-8", errors="replace"))
            ser.flush()
            deadline = time.time() + 1.2
            while time.time() < deadline:
                waiting = getattr(ser, "in_waiting", 0) or 0
                if waiting:
                    rx = ser.readline().decode("utf-8", errors="replace").strip()
                    if rx:
                        print(f"[serial] cmd-rx: {rx}", flush=True)
                        if "OK cmd" in rx or "CMD 수신" in rx:
                            break
                else:
                    time.sleep(0.05)
            print(f"[serial] cmd-tx: {body}", flush=True)
            return True
        except OSError as e:
            print(f"[serial] cmd write fail: {e}", flush=True)
            return False


def _handle_rx_line(text: str) -> None:
    text = text.strip()
    if not text:
        return
    if text.startswith("S:") or text.startswith("S|"):
        _ingest_tele(text)
        return
    if text.startswith("CF_STATUS "):
        st = text.split(None, 1)[-1].strip().lower()
        if st in ("online", "offline"):
            _ingest_status(st)
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
        with _serial_lock:
            if _ser is None or not getattr(_ser, "is_open", False):
                try:
                    _ser = open_serial_no_reset(port)
                    print(f"[serial] open {port}", flush=True)
                except OSError as e:
                    print(f"[serial] open fail: {e}", flush=True)
                    time.sleep(3.0)
                    continue
            ser = _ser
        try:
            raw = ser.readline()
        except OSError as e:
            print(f"[serial] read fail: {e}", flush=True)
            with _serial_lock:
                try:
                    ser.close()
                except OSError:
                    pass
                _ser = None
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
        ok = _write_cmd_line(prefix + payload if prefix else payload)
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
    httpd = ThreadingHTTPServer(("127.0.0.1", API_PORT), CmdHandler)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
