#!/usr/bin/env python3
"""
CronusFarm MQTT 연결 감시 → 접속 불가 시 텔레그램 알림 + (선택) R4 WiFi 자동 복구.

감시 항목:
  1) Mosquitto TCP(기본 127.0.0.1:1883)
  2) Arduino tele 최신 수신(bridge /api/time/status, 기본 45초 초과)
  3) status retain offline 장시간 → USB 시리얼 wifi_set (secrets.h)

환경: /etc/cronusfarm/nodered-telegram.env (토큰·chat_id)
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
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
AUTO_RECOVER = os.environ.get("CRONUSFARM_MQTT_AUTO_RECOVER", "1").strip().lower() in (
    "1",
    "true",
    "yes",
)
AUTO_RECOVER_AFTER_SEC = int(
    os.environ.get("CRONUSFARM_MQTT_AUTO_RECOVER_AFTER_SEC", "180") or 180
)
AUTO_RECOVER_COOLDOWN_SEC = int(
    os.environ.get("CRONUSFARM_MQTT_AUTO_RECOVER_COOLDOWN_SEC", "1800") or 1800
)
R4_ESCALATE_AFTER_SEC = int(
    os.environ.get("CRONUSFARM_MQTT_R4_ESCALATE_AFTER_SEC", "600") or 600
)
R4_ESCALATE_COOLDOWN_SEC = int(
    os.environ.get("CRONUSFARM_MQTT_R4_ESCALATE_COOLDOWN_SEC", "900") or 900
)
AUTO_RECOVER_NOTIFY = os.environ.get(
    "CRONUSFARM_MQTT_AUTO_RECOVER_NOTIFY", "1"
).strip().lower() in ("1", "true", "yes")


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


def fetch_bridge_status(device_id: str) -> tuple[dict | None, str | None]:
    url = f"{BRIDGE_URL}/api/time/status?device_id={urllib.parse.quote(device_id)}"
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace")), None
    except Exception as e:
        return None, str(e)


def check_tele_fresh(device_id: str, stale_sec: int) -> tuple[bool, str | None]:
    j, err = fetch_bridge_status(device_id)
    if j is None:
        return False, f"상태 API 오류: {err}"
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
        f"poll={POLL_SEC}s tele_stale={TELE_STALE_SEC}s "
        f"auto_recover={AUTO_RECOVER} after={AUTO_RECOVER_AFTER_SEC}s "
        f"recover_cd={AUTO_RECOVER_COOLDOWN_SEC}s",
        flush=True,
    )

    mqtt_offline_since: float | None = None
    last_auto_recover_at = 0.0
    tele_stale_since: float | None = None
    last_r4_escalate_at = 0.0

    def maybe_auto_r4_usb_recover(
        tele_stale: int | float, r4_online: bool, usb_online: bool
    ) -> None:
        nonlocal tele_stale_since, last_r4_escalate_at
        if not AUTO_RECOVER:
            return
        stale = int(tele_stale or 0)
        if r4_online or usb_online or stale < R4_ESCALATE_AFTER_SEC:
            tele_stale_since = None
            return
        now = time.time()
        if tele_stale_since is None:
            tele_stale_since = now
            return
        if now - tele_stale_since < R4_ESCALATE_AFTER_SEC:
            return
        if now - last_r4_escalate_at < R4_ESCALATE_COOLDOWN_SEC:
            return
        root = Path(__file__).resolve().parents[1]
        script = root / "scripts" / "pi-recover-r4-escalate.sh"
        if not script.is_file():
            print(f"[recover] missing {script}", flush=True)
            return
        print(
            f"[recover] USB tele stale {stale}s — pi-recover-r4-escalate.sh",
            flush=True,
        )
        try:
            subprocess.run(
                ["bash", str(script)],
                cwd=str(root),
                timeout=420,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            print(f"[recover] r4 escalate failed: {e}", flush=True)
        last_r4_escalate_at = now
        tele_stale_since = now
        if AUTO_RECOVER_NOTIFY and token and chat_id:
            maybe_alert(
                "r4_usb",
                f"R4 USB tele 단절 {stale}s — 자동 단계 복구 실행",
            )

    def maybe_auto_wifi_recover(status: str, tele_stale: int | float) -> None:
        nonlocal mqtt_offline_since, last_auto_recover_at
        if not AUTO_RECOVER:
            return
        st = (status or "").strip().lower()
        if st == "online":
            mqtt_offline_since = None
            return
        now = time.time()
        if mqtt_offline_since is None:
            mqtt_offline_since = now
            return
        offline_for = now - mqtt_offline_since
        if offline_for < AUTO_RECOVER_AFTER_SEC:
            return
        if now - last_auto_recover_at < AUTO_RECOVER_COOLDOWN_SEC:
            return

        print(
            f"[recover] MQTT status={status!r} offline {int(offline_for)}s "
            f"tele_stale={tele_stale}s — 시리얼 WiFi 프로비저닝",
            flush=True,
        )
        try:
            from cronusfarm_mqtt_wifi_recover import run_auto_recover
        except ImportError:
            # Pi: scripts 가 cwd 가 아닐 수 있음
            import sys
            from pathlib import Path

            scripts = Path(__file__).resolve().parent
            if str(scripts) not in sys.path:
                sys.path.insert(0, str(scripts))
            from cronusfarm_mqtt_wifi_recover import run_auto_recover

        ok = run_auto_recover()
        last_auto_recover_at = now
        mqtt_offline_since = now  # 연속 시도 방지 — 쿨다운까지 대기

        if AUTO_RECOVER_NOTIFY and token and chat_id:
            body = (
                f"자동 WiFi 프로비저닝 {'성공' if ok else '실패'}\n"
                f"status={status} offline {int(offline_for)}s\n"
                f"tele_stale={tele_stale}s"
            )
            if ok:
                maybe_recover("auto_wifi", body)
            else:
                maybe_alert("auto_wifi", body)

    while True:
        broker_ok = check_broker_tcp(MQTT_HOST, MQTT_PORT)
        tele_ok, tele_reason = check_tele_fresh(DEVICE_ID, TELE_STALE_SEC)
        armed = (time.time() - started) >= STARTUP_GRACE_SEC

        bridge_j, _ = fetch_bridge_status(DEVICE_ID)
        if armed and bridge_j is not None:
            last_status = str(bridge_j.get("last_status") or "offline")
            tele_stale = int(bridge_j.get("tele_stale_sec") or 9999)
            r4_on = bridge_j.get("r4_online") is True
            usb_on = bridge_j.get("usb_online") is True
            maybe_auto_r4_usb_recover(tele_stale, r4_on, usb_on)
            maybe_auto_wifi_recover(last_status, tele_stale)

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
