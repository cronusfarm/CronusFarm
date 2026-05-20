#!/usr/bin/env python3
"""
CronusFarm MQTT 연결 감시 → 접속 불가 시 텔레그램 즉시 알림.

감시 항목:
  1) Mosquitto TCP(기본 127.0.0.1:1883)
  2) Arduino tele 최신 수신(bridge /api/time/status, 기본 45초 초과)

환경: /etc/cronusfarm/nodered-telegram.env (토큰·chat_id)
"""
from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ENV_FILE = Path(os.environ.get("CRONUSFARM_TELEGRAM_ENV", "/etc/cronusfarm/nodered-telegram.env"))
MQTT_HOST = os.environ.get("CRONUSFARM_MQTT_HOST", "127.0.0.1").strip()
MQTT_PORT = int(os.environ.get("CRONUSFARM_MQTT_PORT", "1883") or 1883)
DEVICE_ID = os.environ.get("CRONUSFARM_DEVICE_ID", "cronusfarm-01").strip()
BRIDGE_URL = os.environ.get("CRONUSFARM_SQLITE_BRIDGE_URL", "http://127.0.0.1:18766").rstrip("/")
POLL_SEC = float(os.environ.get("CRONUSFARM_MQTT_WATCH_SEC", "10"))
TELE_STALE_SEC = int(os.environ.get("CRONUSFARM_MQTT_TELE_STALE_SEC", "45"))
STARTUP_GRACE_SEC = int(os.environ.get("CRONUSFARM_MQTT_WATCH_GRACE_SEC", "90"))
ALERT_COOLDOWN_SEC = int(os.environ.get("CRONUSFARM_MQTT_ALERT_COOLDOWN_SEC", "300"))
RECOVER_NOTIFY = os.environ.get("CRONUSFARM_MQTT_RECOVER_NOTIFY", "1").strip().lower() in (
    "1",
    "true",
    "yes",
)


def load_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        print(f"load_env_file {path}: {e}", flush=True)
        return out
    for line in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def resolve_telegram_creds() -> tuple[str, str]:
    """systemd EnvironmentFile 누락 대비 — 파일 우선."""
    file_env = load_env_file(ENV_FILE)
    token = (
        file_env.get("CRONUSFARM_TELEGRAM_BOT_TOKEN")
        or os.environ.get("CRONUSFARM_TELEGRAM_BOT_TOKEN")
        or ""
    ).strip()
    chat_id = (
        file_env.get("CRONUSFARM_TELEGRAM_CHAT_ID")
        or os.environ.get("CRONUSFARM_TELEGRAM_CHAT_ID")
        or ""
    ).strip()
    return token, chat_id


def telegram_send(token: str, chat_id: str, text: str) -> bool:
    q = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": text[:4000]},
        quote_via=urllib.parse.quote,
    )
    url = f"https://api.telegram.org/bot{token}/sendMessage?{q}"
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
        return bool(body.get("ok"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        print(f"telegram_send failed: {e}", flush=True)
        return False


def check_broker_tcp(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_tele_fresh(device_id: str, stale_sec: int) -> tuple[bool, str | None]:
    url = f"{BRIDGE_URL}/api/time/status?device_id={urllib.parse.quote(device_id)}"
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            j = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        return False, f"상태 API 오류: {e}"
    lt = j.get("last_tele_ts_ms")
    if lt is None or not str(lt).strip():
        return False, "tele 미수신(기록 없음)"
    age = (time.time() * 1000 - int(lt)) / 1000.0
    if age > stale_sec:
        return False, f"tele {int(age)}초 전 (한계 {stale_sec}s)"
    return True, None


def kst_hm() -> str:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S KST")


def main() -> None:
    token, chat_id = resolve_telegram_creds()
    if not token or not chat_id:
        print(
            f"WARN: 텔레그램 미설정 (token={len(token)} chat={len(chat_id)}) "
            f"— {ENV_FILE} 확인",
            flush=True,
        )
    else:
        print(f"telegram ready (chat_id len={len(chat_id)})", flush=True)

    started = time.time()
    prev_broker: bool | None = None
    prev_tele: bool | None = None
    last_alert: dict[str, float] = {}

    def maybe_alert(key: str, text: str) -> None:
        nonlocal token, chat_id
        if not token or not chat_id:
            token, chat_id = resolve_telegram_creds()
        if not token or not chat_id:
            print(f"ALERT skipped (no telegram): {key}", flush=True)
            return
        now = time.time()
        if now - last_alert.get(key, 0) < ALERT_COOLDOWN_SEC:
            return
        full = f"⚠️ CronusFarm MQTT\n{text}\n({kst_hm()})"
        if telegram_send(token, chat_id, full):
            last_alert[key] = now
            print(f"ALERT sent: {key}", flush=True)

    def maybe_recover(key: str, text: str) -> None:
        if not RECOVER_NOTIFY or not token or not chat_id:
            return
        if key not in last_alert:
            return
        full = f"✅ CronusFarm MQTT 복구\n{text}\n({kst_hm()})"
        if telegram_send(token, chat_id, full):
            last_alert.pop(key, None)
            print(f"RECOVER sent: {key}", flush=True)

    print(
        f"mqtt_watch start host={MQTT_HOST}:{MQTT_PORT} device={DEVICE_ID} "
        f"poll={POLL_SEC}s tele_stale={TELE_STALE_SEC}s",
        flush=True,
    )

    while True:
        broker_ok = check_broker_tcp(MQTT_HOST, MQTT_PORT)
        tele_ok, tele_reason = check_tele_fresh(DEVICE_ID, TELE_STALE_SEC)
        armed = (time.time() - started) >= STARTUP_GRACE_SEC

        if armed:
            if prev_broker is None:
                if not broker_ok:
                    maybe_alert(
                        "broker",
                        f"Mosquitto 브로커 접속 불가\n{MQTT_HOST}:{MQTT_PORT}",
                    )
            elif broker_ok != prev_broker:
                if not broker_ok:
                    maybe_alert(
                        "broker",
                        f"Mosquitto 브로커 접속 불가\n{MQTT_HOST}:{MQTT_PORT}",
                    )
                else:
                    maybe_recover(
                        "broker",
                        f"Mosquitto 브로커 정상\n{MQTT_HOST}:{MQTT_PORT}",
                    )

            if prev_tele is None:
                if not tele_ok:
                    maybe_alert(
                        "tele",
                        f"Arduino MQTT tele 단절\n{DEVICE_ID}\n{tele_reason or ''}",
                    )
            elif tele_ok != prev_tele:
                if not tele_ok:
                    maybe_alert(
                        "tele",
                        f"Arduino MQTT tele 단절\n{DEVICE_ID}\n{tele_reason or ''}",
                    )
                else:
                    maybe_recover(
                        "tele",
                        f"Arduino MQTT tele 정상\n{DEVICE_ID}",
                    )

            prev_broker = broker_ok
            prev_tele = tele_ok

        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
