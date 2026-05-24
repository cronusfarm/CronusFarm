#!/usr/bin/env python3
"""
CronusFarm SQLite HTTP 브리지 (표준 라이브러리만 사용).
Pi에서 Node-RED가 tele/cmd를 POST하면 SQLite에 적재합니다.

환경변수:
  CRONUSFARM_SQLITE_PATH  DB 파일 경로 (기본: ~/.node-red/cronusfarm.sqlite)
  CRONUSFARM_BRIDGE_HOST  바인드 주소 (기본: 127.0.0.1; systemd 예시는 0.0.0.0 으로 Tailscale/LAN 원격 허용)
  CRONUSFARM_BRIDGE_PORT  포트 (기본: 18766)
  CRONUSFARM_SCHEDULE_MQTT  0/false/off 시에만 SCHED_JSON MQTT 발행 생략(그 외는 기본 발행, mosquitto_pub 필요)
  CRONUSFARM_MQTT_HOST      mosquitto_pub -h (기본: 127.0.0.1). 로컬 PC에서 Pi Mosquitto로 SCHED_JSON 등 보낼 때 ida.mango-larch.ts.net
  CRONUSFARM_MQTT_PORT      mosquitto_pub -p (기본: 1883, WAN 51883)
  CRONUSFARM_BOOT_SCHED_SYNC_SEC  R4 status=online 후 DB 스케줄→MQTT 재발행 지연(초, 기본 60)

POST /ingest/tele  JSON: { device_id, topic?, raw, ts_ms? }
POST /ingest/cmd   JSON: { device_id, topic?, payload, ts_ms? }
POST /ingest/status JSON: { device_id, topic?, payload, ts_ms? }
POST /settings/kv JSON: { device_id, key, value }
GET  /health
GET  /api/snapshot?device_id=...  JSON: tele/cmd 건수·마지막 tele 시각·settings_kv 목록
GET  /api/schedule?device_id=...&channel=...  JSON: schedule_rule 목록
GET  /api/schedule/batch?device_id=...  JSON: { channels: { ch: { rules, rule_count } } } 전 채널 1회
PUT  /api/schedule?device_id=...&channel=...  JSON: rules[] 에 rule_kind(window|cycle), window 시 on_min/off_min(분), cycle 시 on_sec/off_sec(초)·선택 on_min/off_min(시간대)
POST /api/schedule/seed_defaults  JSON: { device_id?, force? } 기본 스케줄 DB 시드
GET  /api/channel/timeline?device_id=...&channel=...&hours=24  JSON: tele_channel_fact 시계열(그래프). anchor_ts_ms=창 시작(ms), points는 창 시작·끝 보간 포함
GET  /api/channel/timeline/batch?device_id=...&channels=led_a1,pump_a1,...&hours=24  JSON: { channels: { ch: { points, ... } } } (느린 WAN/TS 왕복 1회로 Bed 전체)
POST /api/channel/backfill  JSON: { device_id, channel|channel_key, hours? } tele_sample→tele_channel_fact 누락 행 보강
GET  /api/channel/status?device_id=...  JSON: 채널별 최신 state·auto_mode(마지막 tele 적재)
POST /api/channel-action  JSON: { device_id, channel, action } → SQLite + MQTT cmd(Arduino)
GET  /api/audit_log?device_id=...&limit=100&channel=&since_ms=0  JSON: manual_switch_event 감사 로그(수동·스케줄 저장·자동 ON/OFF)
POST /ingest/manual_event  JSON: UI 수동 조작 로그 → manual_switch_event (source: ui|system|…)
POST /ingest/sensor  JSON: PHW3988 등 → sensor_reading (ph, ec, temp_c, zone, raw_json)
POST /ingest/telegram-register  JSON: { chat_id, display_name?, telegram_username? } 텔레그램 알림 신청(pending)
GET  /api/sensor/latest?device_id=...&zone=phw3988  JSON: 최신 sensor_reading 1건
GET  /api/admin/me|members|telegram-users|notify-prefs|news|farm-diary|pest-forecast
POST /api/admin/members|telegram-users|notify-prefs|farm-diary|ai-diagnose|news/seed
PUT  /api/admin/members|telegram-users|notify-prefs
DELETE /api/admin/farm-diary|telegram-users?id=
OPTIONS  CORS 프리플라이트 (브라우저에서 dashboard→브리지 fetch용)
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from pathlib import Path
import urllib.error
import urllib.request
from urllib.parse import parse_qs, quote, urlparse

# 타임라인 batch 동시 1건만 — 다중 탭·폴링이 SQLite 단일 conn을 막아 /ui·status 타임아웃 방지
_timeline_batch_slots = threading.Semaphore(
    max(1, int(os.environ.get("CRONUSFARM_TIMELINE_BATCH_MAX", "1") or "1"))
)


def _open_sqlite_read(db_path: Path) -> sqlite3.Connection:
    """읽기 전용 요청용 별도 연결(WAL) — ingest·batch와 write conn 분리."""
    c = sqlite3.connect(str(db_path), timeout=5.0, check_same_thread=False)
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA busy_timeout=5000")
    try:
        c.execute("PRAGMA journal_mode=WAL")
    except sqlite3.Error:
        pass
    return c


def _configure_sqlite_conn(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.Error:
        pass


# 기존 DB에 schedule_rule 없을 때 런타임 보강
_SCHEDULE_RULE_DDL = """
CREATE TABLE IF NOT EXISTS schedule_rule (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL,
  channel_key TEXT NOT NULL,
  dow_mask INTEGER NOT NULL DEFAULT 127,
  slot_index INTEGER NOT NULL DEFAULT 0,
  on_min INTEGER NOT NULL DEFAULT 0,
  off_min INTEGER NOT NULL DEFAULT 0,
  enabled INTEGER NOT NULL DEFAULT 1,
  rule_kind TEXT NOT NULL DEFAULT 'window',
  on_sec INTEGER,
  off_sec INTEGER,
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (device_id) REFERENCES device(device_id)
);
CREATE INDEX IF NOT EXISTS idx_schedule_rule_dev_ch ON schedule_rule(device_id, channel_key);
"""


def _ensure_schedule_rule_table(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schedule_rule'"
    )
    if not cur.fetchone():
        conn.executescript(_SCHEDULE_RULE_DDL)
    _ensure_schedule_rule_columns(conn)


def _schedule_rule_entry_from_row(r: tuple) -> dict[str, object]:
    """SELECT id, dow_mask, slot_index, on_min, off_min, enabled, updated_at, rule_kind, on_sec, off_sec."""
    rk = str(r[7] or "window")
    entry: dict[str, object] = {
        "id": int(r[0]),
        "dow_mask": int(r[1]),
        "slot_index": int(r[2]),
        "on_min": int(r[3]),
        "off_min": int(r[4]),
        "enabled": int(r[5]),
        "updated_at": r[6],
        "rule_kind": rk,
    }
    if rk == "cycle":
        entry["on_sec"] = int(r[8]) if r[8] is not None else 0
        entry["off_sec"] = int(r[9]) if r[9] is not None else 0
    else:
        entry["on_sec"] = None
        entry["off_sec"] = None
    return entry


def _fetch_schedule_rules_by_channel(
    cur: sqlite3.Cursor, device_id: str
) -> dict[str, list[dict[str, object]]]:
    cur.execute(
        """SELECT channel_key, id, dow_mask, slot_index, on_min, off_min, enabled, updated_at,
                  COALESCE(rule_kind, 'window'), on_sec, off_sec
           FROM schedule_rule
           WHERE device_id=?
           ORDER BY channel_key, slot_index, id""",
        (device_id,),
    )
    out: dict[str, list[dict[str, object]]] = {}
    for row in cur.fetchall():
        ch = str(row[0])
        entry = _schedule_rule_entry_from_row(row[1:])
        out.setdefault(ch, []).append(entry)
    return out


def _ensure_schedule_rule_columns(conn: sqlite3.Connection) -> None:
    """기존 DB: schedule_rule 확장(window / 주기 cycle)."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(schedule_rule)")
    cols = {row[1] for row in cur.fetchall()}
    if not cols:
        return
    if "rule_kind" not in cols:
        cur.execute(
            "ALTER TABLE schedule_rule ADD COLUMN rule_kind TEXT NOT NULL DEFAULT 'window'"
        )
    if "on_sec" not in cols:
        cur.execute("ALTER TABLE schedule_rule ADD COLUMN on_sec INTEGER")
    if "off_sec" not in cols:
        cur.execute("ALTER TABLE schedule_rule ADD COLUMN off_sec INTEGER")
    conn.commit()


def _mqtt_republish_tele(device_id: str, raw: str, topic: str = "") -> str:
    """HTTP ingest tele → Node-RED 구독용 MQTT tele 토픽 재발행."""
    flag = os.environ.get("CRONUSFARM_INGEST_REPUBLISH_MQTT", "1").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return "skipped_env"
    if not raw.strip():
        return "empty"
    exe = shutil.which("mosquitto_pub")
    if not exe:
        return "no_mosquitto_pub"
    host = os.environ.get("CRONUSFARM_MQTT_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = os.environ.get("CRONUSFARM_MQTT_PORT", "1883").strip() or "1883"
    tp = (topic or "").strip() or f"cronusfarm/{device_id}/tele"
    try:
        subprocess.run(
            [exe, "-h", host, "-p", port, "-t", tp, "-m", raw],
            check=False,
            timeout=8,
            capture_output=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "publish_error"
    return "published"


def _r4_publish_cmd_serial(device_id: str, payload: str) -> str:
    """R4 USB 시리얼 데몬(18767)으로 cmd 전달."""
    base = os.environ.get(
        "CRONUSFARM_R4_SERIAL_API_URL", "http://127.0.0.1:18767"
    ).rstrip("/")
    url = f"{base}/r4/cmd"
    body = json.dumps(
        {"device_id": device_id, "payload": payload}, ensure_ascii=False
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            if 200 <= resp.status < 300:
                try:
                    j = json.loads(raw)
                    if j.get("ok"):
                        return "serial_ok"
                except json.JSONDecodeError:
                    return "serial_ok"
            return "serial_rejected"
    except (urllib.error.URLError, TimeoutError, OSError):
        return "serial_error"


def _mqtt_publish_cmd(device_id: str, payload: str) -> str:
    """Arduino cmd — MQTT 또는 USB 시리얼(환경 CRONUSFARM_R4_CMD_TRANSPORT)."""
    transport = os.environ.get("CRONUSFARM_R4_CMD_TRANSPORT", "mqtt").strip().lower()
    if transport in ("serial", "usb", "usb-serial"):
        return _r4_publish_cmd_serial(device_id, payload)
    flag = os.environ.get("CRONUSFARM_CMD_MQTT", "").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return "skipped_env"
    exe = shutil.which("mosquitto_pub")
    if not exe:
        return "no_mosquitto_pub"
    host = os.environ.get("CRONUSFARM_MQTT_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = os.environ.get("CRONUSFARM_MQTT_PORT", "1883").strip() or "1883"
    topic = f"cronusfarm/{device_id}/cmd"
    try:
        subprocess.run(
            [exe, "-h", host, "-p", port, "-t", topic, "-m", payload],
            check=False,
            timeout=8,
            capture_output=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "publish_error"
    return "published"


def _channel_action_mqtt_parts(channel_key: str, action: str, body: dict) -> list[str]:
    """UI channel-action → Arduino cmd (ui_<ch>=0|1|2). auto_=0 MQTT 단독은 펌웨어에서 무시됨."""
    ch = channel_key.strip()
    act = action.strip()
    parts: list[str] = []

    def _ui_val() -> int:
        onv = body.get("on")
        if onv in (True, 1, "1", "on", "true"):
            return 1
        if onv in (False, 0, "0", "off", "false"):
            return 0
        ns = body.get("new_state")
        if ns in (0, 1):
            return int(ns)
        ps = body.get("prev_state")
        if ps in (0, 1):
            return int(ps)
        return 0

    if act == "set_output":
        parts.append(f"ui_{ch}={_ui_val()}")
    elif act == "set_auto":
        parts.append(f"ui_{ch}=2")
    elif act == "set_manual":
        parts.append(f"ui_{ch}={_ui_val()}")
    elif act == "revert_auto":
        parts.append(f"ui_{ch}=2")
    return parts


def _mqtt_rule_for_publish(rule: dict[str, object]) -> dict[str, object]:
    """Arduino SCHED_JSON 파서 호환 — window는 on_sec/off_sec null 제외."""
    rk = str(rule.get("rule_kind") or "window").strip().lower()
    out: dict[str, object] = {
        "rule_kind": rk,
        "dow_mask": int(rule.get("dow_mask") or 127),
        "slot_index": int(rule.get("slot_index") or 0),
        "on_min": int(rule.get("on_min") or 0),
        "off_min": int(rule.get("off_min") or 0),
        "enabled": int(rule.get("enabled", 1) or 0),
    }
    if rk == "cycle":
        out["on_sec"] = int(rule.get("on_sec") or 0)
        out["off_sec"] = int(rule.get("off_sec") or 0)
    return out


def _publish_schedule_mqtt(
    *,
    device_id: str,
    channel_key: str,
    rules: list[dict[str, object]],
) -> tuple[str, int]:
    """PUT /api/schedule 직후 Arduino cmd 토픽으로 SCHED_JSON + auto 발행."""
    sch_ver = int(time.time())
    flag = os.environ.get("CRONUSFARM_SCHEDULE_MQTT", "").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return ("skipped_env", sch_ver)
    enabled = [r for r in rules if int(r.get("enabled", 1) or 0)]
    mqtt_rules = [_mqtt_rule_for_publish(r) for r in enabled]
    envelope = {
        "sch_ver": sch_ver,
        "channel": channel_key,
        "rules": mqtt_rules,
    }
    raw_j = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
    payload = "SCHED_JSON=" + quote(raw_j, safe="")
    st = _mqtt_publish_cmd(device_id, payload)
    if enabled and st == "published":
        _mqtt_publish_cmd(device_id, f"auto_{channel_key}=1")
    return (st, sch_ver)


_boot_schedule_sync_timers: dict[str, threading.Timer] = {}
_boot_schedule_sync_lock = threading.Lock()
_hold_revert_timers: dict[str, threading.Timer] = {}
_hold_revert_lock = threading.Lock()
_revert_grace_until: dict[str, float] = {}
_revert_grace_lock = threading.Lock()


def _hold_timer_key(device_id: str, channel_key: str) -> str:
    return f"{device_id}:{channel_key}"


def _cancel_hold_revert(device_id: str, channel_key: str) -> None:
    with _hold_revert_lock:
        old = _hold_revert_timers.pop(_hold_timer_key(device_id, channel_key), None)
    if old is not None:
        old.cancel()


def _set_revert_grace(device_id: str, channel_key: str, seconds: float = 180.0) -> None:
    """복귀 직후 tele이 auto=0으로 DB를 덮어쓰지 않도록 잠시 auto=1 유지."""
    key = _hold_timer_key(device_id, channel_key)
    with _revert_grace_lock:
        _revert_grace_until[key] = time.time() + max(30.0, float(seconds))


def _in_revert_grace(device_id: str, channel_key: str) -> bool:
    key = _hold_timer_key(device_id, channel_key)
    with _revert_grace_lock:
        until = _revert_grace_until.get(key)
    return until is not None and time.time() < until


def _read_hold_expires_ms(
    conn: sqlite3.Connection, device_id: str, channel_key: str
) -> int | None:
    _ensure_channel_manual_hold_table(conn)
    cur = conn.cursor()
    cur.execute(
        "SELECT expires_ms FROM channel_manual_hold WHERE device_id=? AND channel_key=?",
        (device_id, channel_key),
    )
    row = cur.fetchone()
    return int(row[0]) if row else None


def _effective_auto_for_tele(
    conn: sqlite3.Connection,
    device_id: str,
    channel_key: str,
    auto_i: int | None,
    ts_ms: int,
    prev_au: int | None,
) -> int:
    if _in_revert_grace(device_id, channel_key):
        return 1
    hold_exp = _read_hold_expires_ms(conn, device_id, channel_key)
    if hold_exp is not None and hold_exp > ts_ms:
        if auto_i in (0, 1):
            return int(auto_i)
        if prev_au is not None:
            return int(prev_au)
        return 0
    if hold_exp is not None and hold_exp <= ts_ms:
        _delete_channel_hold(conn, device_id, channel_key)
    if auto_i in (0, 1):
        return int(auto_i)
    if prev_au is not None:
        return int(prev_au)
    return 1


_CHANNEL_HOLD_DDL = """
CREATE TABLE IF NOT EXISTS channel_manual_hold (
  device_id TEXT NOT NULL,
  channel_key TEXT NOT NULL,
  expires_ms INTEGER NOT NULL,
  hold_minutes INTEGER NOT NULL,
  updated_ms INTEGER NOT NULL,
  PRIMARY KEY (device_id, channel_key)
);
CREATE INDEX IF NOT EXISTS idx_cmh_expires ON channel_manual_hold(expires_ms);
"""


def _ensure_channel_manual_hold_table(conn: sqlite3.Connection) -> None:
    conn.executescript(_CHANNEL_HOLD_DDL)


def _default_hold_minutes() -> int:
    raw = os.environ.get("CRONUSFARM_DEFAULT_HOLD_MIN", "30").strip() or "30"
    try:
        v = int(raw)
    except ValueError:
        v = 30
    return max(1, min(v, 60))


def _panel_hold_minutes() -> int:
    """패널(2004A) 엔코더 MAN·ON/OFF → tele auto=0 시 자동 복귀 상한."""
    raw = os.environ.get("CRONUSFARM_PANEL_HOLD_MIN", "60").strip() or "60"
    try:
        v = int(raw)
    except ValueError:
        v = 60
    return max(1, min(v, 60))


def _should_refresh_panel_hold(
    *,
    auto_i: int | None,
    prev_au: int | None,
    db_au: int | None,
    state_i: int,
    db_st: int | None,
    hold_exp: int | None,
    ts_ms: int,
) -> bool:
    """tele auto=0 전환 시에만 패널 홀드(1h). 이미 수동인 채널에 홀드를 반복 갱신하지 않음."""
    if auto_i != 0:
        return False
    if hold_exp is not None and hold_exp > ts_ms:
        return False
    if prev_au == 1 or db_au == 1:
        return True
    if db_st is not None and state_i != db_st and (db_au == 1 or prev_au == 1):
        return True
    return False


def _normalize_hold_minutes(hold_minutes: object | None) -> int:
    if hold_minutes is None:
        return _default_hold_minutes()
    try:
        hm = int(hold_minutes)
    except (TypeError, ValueError):
        return _default_hold_minutes()
    return max(1, min(hm, 60))


def _upsert_channel_hold(
    conn: sqlite3.Connection, device_id: str, channel_key: str, hold_minutes: int
) -> int:
    _ensure_channel_manual_hold_table(conn)
    now_ms = int(time.time() * 1000)
    exp = now_ms + hold_minutes * 60 * 1000
    conn.execute(
        """INSERT INTO channel_manual_hold
           (device_id, channel_key, expires_ms, hold_minutes, updated_ms)
           VALUES (?,?,?,?,?)
           ON CONFLICT(device_id, channel_key) DO UPDATE SET
             expires_ms=excluded.expires_ms,
             hold_minutes=excluded.hold_minutes,
             updated_ms=excluded.updated_ms""",
        (device_id, channel_key, exp, hold_minutes, now_ms),
    )
    return exp


def _delete_channel_hold(conn: sqlite3.Connection, device_id: str, channel_key: str) -> None:
    _ensure_channel_manual_hold_table(conn)
    conn.execute(
        "DELETE FROM channel_manual_hold WHERE device_id=? AND channel_key=?",
        (device_id, channel_key),
    )


def _read_channel_hold_minutes(
    conn: sqlite3.Connection, device_id: str, channel_key: str
) -> int | None:
    _ensure_channel_manual_hold_table(conn)
    cur = conn.cursor()
    cur.execute(
        "SELECT hold_minutes FROM channel_manual_hold WHERE device_id=? AND channel_key=?",
        (device_id, channel_key),
    )
    row = cur.fetchone()
    return int(row[0]) if row else None


def _revert_channel_to_auto(
    db_path: Path, lock: threading.Lock, device_id: str, channel_key: str
) -> None:
    """홀드 만료·스위퍼: MQTT auto=1 + DB tele/감사 반영."""
    _cancel_hold_revert(device_id, channel_key)
    _set_revert_grace(device_id, channel_key)
    _mqtt_publish_cmd(device_id, f"auto_{channel_key}=1")
    with lock:
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            _ensure_manual_switch_event_table(conn)
            _ensure_device(conn, device_id)
            ts_ms = int(time.time() * 1000)
            cur = conn.cursor()
            cur.execute(
                """SELECT state, auto_mode FROM tele_channel_fact
                   WHERE device_id=? AND channel_key=? ORDER BY ts_ms DESC LIMIT 1""",
                (device_id, channel_key),
            )
            row = cur.fetchone()
            cur_st = int(row[0]) if row and row[0] is not None else 0
            prev_au = int(row[1]) if row and row[1] is not None else 0
            if prev_au == 1:
                _delete_channel_hold(conn, device_id, channel_key)
                conn.commit()
                return
            _insert_manual_switch_event(
                conn,
                device_id=device_id,
                channel_key=channel_key,
                source="hold_expire",
                ts_ms=ts_ms,
                prev_auto=0,
                new_auto=1,
                prev_state=cur_st,
                new_state=cur_st,
                meta={"action": "revert_auto", "reason": "hold_expired"},
            )
            conn.execute(
                """INSERT INTO tele_channel_fact
                   (device_id, ts_ms, channel_key, state, auto_mode, on_sec, off_sec)
                   VALUES (?,?,?,?,?,?,?)""",
                (device_id, ts_ms, channel_key, cur_st, 1, None, None),
            )
            _delete_channel_hold(conn, device_id, channel_key)
            conn.commit()
        finally:
            conn.close()


def _arm_hold_timer_at_expiry(
    db_path: Path,
    lock: threading.Lock,
    device_id: str,
    channel_key: str,
    expires_ms: int,
) -> None:
    _cancel_hold_revert(device_id, channel_key)
    delay = max(1.0, (int(expires_ms) - int(time.time() * 1000)) / 1000.0)

    def _fire() -> None:
        try:
            _revert_channel_to_auto(db_path, lock, device_id, channel_key)
        except Exception as e:
            print(f"hold timer revert {device_id}/{channel_key}: {e}", flush=True)
        with _hold_revert_lock:
            _hold_revert_timers.pop(_hold_timer_key(device_id, channel_key), None)

    timer = threading.Timer(delay, _fire)
    timer.daemon = True
    with _hold_revert_lock:
        _hold_revert_timers[_hold_timer_key(device_id, channel_key)] = timer
    timer.start()


def _hold_sweeper_loop(db_path: Path, lock: threading.Lock, interval_sec: float = 15.0) -> None:
    while True:
        time.sleep(interval_sec)
        now_ms = int(time.time() * 1000)
        with lock:
            conn = sqlite3.connect(str(db_path), check_same_thread=False)
            try:
                _ensure_channel_manual_hold_table(conn)
                cur = conn.cursor()
                cur.execute(
                    "SELECT device_id, channel_key FROM channel_manual_hold WHERE expires_ms <= ?",
                    (now_ms,),
                )
                expired = list(cur.fetchall())
            finally:
                conn.close()
        for device_id, channel_key in expired:
            try:
                _revert_channel_to_auto(
                    db_path, lock, str(device_id), str(channel_key)
                )
            except Exception as e:
                print(
                    f"hold sweeper {device_id}/{channel_key}: {e}",
                    flush=True,
                )
        _sweep_revert_manual_without_hold(db_path, lock, now_ms)


def _sweep_revert_manual_without_hold(
    db_path: Path, lock: threading.Lock, now_ms: int | None = None
) -> None:
    """홀드 없이 오래 수동(tele)인 채널만 자동 복귀 — UI/패널 수동 직후 오동작 방지."""
    if now_ms is None:
        now_ms = int(time.time() * 1000)
    with lock:
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        try:
            _ensure_channel_manual_hold_table(conn)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT t.device_id, t.channel_key
                FROM tele_channel_fact t
                INNER JOIN (
                  SELECT device_id, channel_key, MAX(ts_ms) AS mx
                  FROM tele_channel_fact
                  GROUP BY device_id, channel_key
                ) u ON t.device_id = u.device_id
                   AND t.channel_key = u.channel_key AND t.ts_ms = u.mx
                LEFT JOIN channel_manual_hold h
                  ON h.device_id = t.device_id
                 AND h.channel_key = t.channel_key
                 AND h.expires_ms > ?
                WHERE t.auto_mode = 0 AND h.channel_key IS NULL
                  AND t.ts_ms < ?
                """,
                (now_ms, now_ms - _default_hold_minutes() * 60 * 1000),
            )
            rows = list(cur.fetchall())
        finally:
            conn.close()
    for device_id, channel_key in rows:
        dev, ch = str(device_id), str(channel_key)
        if _in_revert_grace(dev, ch):
            continue
        try:
            _revert_channel_to_auto(db_path, lock, dev, ch)
        except Exception as e:
            print(f"sweep manual→auto {dev}/{ch}: {e}", flush=True)


def _hold_is_ui_intentional(
    conn: sqlite3.Connection, device_id: str, channel_key: str
) -> bool:
    """현재 홀드를 만든 최신 ui/panel 이벤트가 UI 수동인지 (과거 UI 이력 무시)."""
    cur = conn.cursor()
    cur.execute(
        """SELECT source, meta_json FROM manual_switch_event
        WHERE device_id=? AND channel_key=? AND source IN ('ui', 'panel')
        ORDER BY ts_ms DESC LIMIT 1""",
        (device_id, channel_key),
    )
    row = cur.fetchone()
    if not row or str(row[0]) != "ui":
        return False
    try:
        meta = json.loads(row[1] or "{}")
    except json.JSONDecodeError:
        meta = {}
    return meta.get("action") in ("set_manual", "set_output")


def _clear_non_ui_holds(
    db_path: Path, lock: threading.Lock, device_id: str
) -> list[str]:
    """UI set_manual 없이 붙은 홀드(패널·tele 등) 제거."""
    cleared: list[str] = []
    with lock:
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        try:
            _ensure_channel_manual_hold_table(conn)
            _ensure_manual_switch_event_table(conn)
            cur = conn.cursor()
            cur.execute(
                "SELECT channel_key FROM channel_manual_hold WHERE device_id=?",
                (device_id,),
            )
            for ch in [str(r[0]) for r in cur.fetchall()]:
                if _hold_is_ui_intentional(conn, device_id, ch):
                    continue
                _delete_channel_hold(conn, device_id, ch)
                cleared.append(ch)
            conn.commit()
        finally:
            conn.close()
    return cleared


def _ensure_auto_mode_unless_hold(
    db_path: Path, lock: threading.Lock, device_id: str
) -> dict:
    """tele 수동(auto_mode=0)인데 유효 홀드가 없으면 스케줄 자동 복귀."""
    panel_cleared = _clear_non_ui_holds(db_path, lock, device_id)
    now_ms = int(time.time() * 1000)
    manual: list[str] = []
    skipped_hold: list[str] = []
    with lock:
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT t.channel_key
                FROM tele_channel_fact t
                INNER JOIN (
                  SELECT device_id, channel_key, MAX(ts_ms) AS mx
                  FROM tele_channel_fact
                  WHERE device_id = ?
                  GROUP BY device_id, channel_key
                ) u ON t.device_id = u.device_id
                   AND t.channel_key = u.channel_key AND t.ts_ms = u.mx
                WHERE t.device_id = ? AND t.auto_mode = 0
                """,
                (device_id, device_id),
            )
            manual = [str(r[0]) for r in cur.fetchall()]
            for ch in manual:
                exp = _read_hold_expires_ms(conn, device_id, ch)
                if exp is not None and int(exp) > now_ms:
                    skipped_hold.append(ch)
        finally:
            conn.close()
    reverted: list[str] = []
    for ch in manual:
        if ch in skipped_hold:
            continue
        try:
            _revert_channel_to_auto(db_path, lock, device_id, ch)
            reverted.append(ch)
        except Exception as e:
            print(f"ensure_auto {device_id}/{ch}: {e}", flush=True)
    return {
        "ok": True,
        "device_id": device_id,
        "panel_holds_cleared": panel_cleared,
        "reverted": reverted,
        "skipped_hold": skipped_hold,
        "n_reverted": len(reverted),
    }


def _revert_stale_manual_channels(
    db_path: Path, lock: threading.Lock, max_age_min: int | None = None
) -> None:
    """tele·홀드 없이 오래 수동인 채널(과거 버그) 일괄 자동 복귀."""
    age = max_age_min if max_age_min is not None else _default_hold_minutes()
    cutoff = int(time.time() * 1000) - age * 60 * 1000
    with lock:
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT t.device_id, t.channel_key
                FROM tele_channel_fact t
                INNER JOIN (
                  SELECT device_id, channel_key, MAX(ts_ms) AS mx
                  FROM tele_channel_fact
                  GROUP BY device_id, channel_key
                ) u ON t.device_id = u.device_id
                   AND t.channel_key = u.channel_key AND t.ts_ms = u.mx
                WHERE t.auto_mode = 0 AND t.ts_ms < ?
                """,
                (cutoff,),
            )
            stale = list(cur.fetchall())
        finally:
            conn.close()
    for device_id, channel_key in stale:
        try:
            _revert_channel_to_auto(db_path, lock, str(device_id), str(channel_key))
        except Exception as e:
            print(f"stale manual revert {device_id}/{channel_key}: {e}", flush=True)


def _recover_hold_timers(db_path: Path, lock: threading.Lock) -> None:
    """브리지 재시작 후 DB 홀드 행 기준 타이머·만료 즉시 복귀."""
    now_ms = int(time.time() * 1000)
    with lock:
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        try:
            _ensure_channel_manual_hold_table(conn)
            cur = conn.cursor()
            cur.execute(
                "SELECT device_id, channel_key, expires_ms FROM channel_manual_hold"
            )
            rows = list(cur.fetchall())
        finally:
            conn.close()
    for device_id, channel_key, exp_ms in rows:
        dev = str(device_id)
        ch = str(channel_key)
        if int(exp_ms) <= now_ms:
            try:
                _revert_channel_to_auto(db_path, lock, dev, ch)
            except Exception as e:
                print(f"hold recover expired {dev}/{ch}: {e}", flush=True)
        else:
            _arm_hold_timer_at_expiry(db_path, lock, dev, ch, int(exp_ms))


def _boot_schedule_sync_delay_sec() -> float:
    raw = os.environ.get("CRONUSFARM_BOOT_SCHED_SYNC_SEC", "60").strip() or "60"
    try:
        v = float(raw)
        return max(5.0, min(v, 600.0))
    except ValueError:
        return 60.0


def force_device_all_auto(
    db_path: Path, lock: threading.Lock, device_id: str
) -> dict[str, object]:
    """cmd retain 제거 + DB 홀드 삭제 + SCHED 동기화 + 전 채널 AUTO MQTT."""
    host = os.environ.get("CRONUSFARM_MQTT_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = os.environ.get("CRONUSFARM_MQTT_PORT", "1883").strip() or "1883"
    topic = f"cronusfarm/{device_id}/cmd"
    exe = shutil.which("mosquitto_pub")
    retain_cleared = False
    if exe:
        try:
            subprocess.run(
                [exe, "-h", host, "-p", port, "-t", topic, "-r", "-n"],
                check=False,
                timeout=8,
                capture_output=True,
            )
            retain_cleared = True
        except (OSError, subprocess.TimeoutExpired):
            pass
        _mqtt_publish_cmd(device_id, "FORCE_AUTO_ALL=1")
        time.sleep(0.35)
    wconn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=5.0)
    try:
        _configure_sqlite_conn(wconn)
        with lock:
            _ensure_channel_manual_hold_table(wconn)
            wconn.execute(
                "DELETE FROM channel_manual_hold WHERE device_id=?",
                (device_id,),
            )
            wconn.commit()
            n, auto_n = _sync_device_schedules_mqtt_full(
                wconn, db_path, lock, device_id
            )
    finally:
        wconn.close()
    return {
        "device_id": device_id,
        "retain_cleared": retain_cleared,
        "channels_published": n,
        "auto_published": auto_n,
    }


def force_device_all_manual_on(
    db_path: Path, lock: threading.Lock, device_id: str
) -> dict[str, object]:
    """개발·점검용: 전 채널 수동 ON (ui_<ch>=1, 펌웨어 패널과 동일 경로)."""
    parts = [f"ui_{ch}=1" for ch in ALL_CHANNELS]
    payload = " ".join(parts)
    st = _mqtt_publish_cmd(device_id, payload)
    with lock:
        conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=5.0)
        try:
            _configure_sqlite_conn(conn)
            _ensure_channel_manual_hold_table(conn)
            _ensure_device(conn, device_id)
            for ch in ALL_CHANNELS:
                _upsert_channel_hold(conn, device_id, ch, 60)
            conn.commit()
        finally:
            conn.close()
    return {
        "device_id": device_id,
        "mqtt": st,
        "cmd_preview": payload[:120] + ("…" if len(payload) > 120 else ""),
        "channels": len(ALL_CHANNELS),
    }


def _mqtt_publish_all_auto(
    db_path: Path | None, lock: threading.Lock | None, device_id: str
) -> int:
    """전 채널 auto_{ch}=1 MQTT 발행 + 만료 홀드 행 정리. 반환: 발행 성공 수."""
    if db_path is not None and lock is not None:
        with lock:
            conn = sqlite3.connect(str(db_path), check_same_thread=False)
            try:
                _ensure_channel_manual_hold_table(conn)
                conn.execute(
                    "DELETE FROM channel_manual_hold WHERE device_id=?",
                    (device_id,),
                )
                conn.commit()
            finally:
                conn.close()
    n = 0
    for ch in ALL_CHANNELS:
        if _mqtt_publish_cmd(device_id, f"auto_{ch}=1") == "published":
            n += 1
        time.sleep(0.04)
    return n


def _sync_device_schedules_mqtt(conn: sqlite3.Connection, device_id: str) -> int:
    """DB schedule_rule 전 채널 → MQTT SCHED_JSON + 전 채널 자동모드. 반환: SCHED_JSON 발행 채널 수."""
    _ensure_schedule_rule_table(conn)
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT channel_key FROM schedule_rule WHERE device_id=?",
        (device_id,),
    )
    db_ch = {str(r[0]) for r in cur.fetchall()}
    channels = [ch for ch in ALL_CHANNELS if ch in db_ch]
    published = 0
    for channel in channels:
        cur.execute(
            """SELECT dow_mask, slot_index, on_min, off_min, enabled,
                      COALESCE(rule_kind, 'window'), on_sec, off_sec
               FROM schedule_rule
               WHERE device_id=? AND channel_key=?
               ORDER BY slot_index, id""",
            (device_id, channel),
        )
        mqtt_rules: list[dict[str, object]] = []
        for r in cur.fetchall():
            rk = str(r[5] or "window").strip().lower()
            en = int(r[4])
            dow = int(r[0])
            if rk == "cycle":
                mqtt_rules.append(
                    {
                        "rule_kind": "cycle",
                        "dow_mask": dow,
                        "slot_index": int(r[1]),
                        "on_min": int(r[2]),
                        "off_min": int(r[3]),
                        "on_sec": int(r[6]) if r[6] is not None else 0,
                        "off_sec": int(r[7]) if r[7] is not None else 0,
                        "enabled": en,
                    }
                )
            else:
                mqtt_rules.append(
                    {
                        "rule_kind": "window",
                        "dow_mask": dow,
                        "slot_index": int(r[1]),
                        "on_min": int(r[2]),
                        "off_min": int(r[3]),
                        "on_sec": None,
                        "off_sec": None,
                        "enabled": en,
                    }
                )
        enabled_rules = [r for r in mqtt_rules if int(r.get("enabled", 0))]
        if not enabled_rules:
            continue
        st, _ = _publish_schedule_mqtt(
            device_id=device_id,
            channel_key=channel,
            rules=enabled_rules,
        )
        if st == "published":
            published += 1
        time.sleep(0.06)
    return published


def _sync_device_schedules_mqtt_full(
    conn: sqlite3.Connection,
    db_path: Path,
    lock: threading.Lock,
    device_id: str,
) -> tuple[int, int]:
    """SCHED_JSON 동기화 + 전 채널 자동 모드. (published, auto_sent)"""
    published = _sync_device_schedules_mqtt(conn, device_id)
    auto_sent = _mqtt_publish_all_auto(db_path, lock, device_id)
    return published, auto_sent


def _run_boot_schedule_sync(db_path: Path, device_id: str) -> None:
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys = ON")
        _ensure_device(conn, device_id)
        n, _ = _sync_device_schedules_mqtt_full(
            conn, db_path, threading.Lock(), device_id
        )
        print(f"[boot-sync] {device_id} SCHED_JSON channels={n}", flush=True)
    except Exception as e:
        print(f"[boot-sync] {device_id} error: {e}", flush=True)
    finally:
        if conn is not None:
            try:
                conn.close()
            except OSError:
                pass
        with _boot_schedule_sync_lock:
            _boot_schedule_sync_timers.pop(device_id, None)


def _arm_boot_schedule_sync(db_path: Path, device_id: str) -> None:
    delay = _boot_schedule_sync_delay_sec()
    with _boot_schedule_sync_lock:
        old = _boot_schedule_sync_timers.pop(device_id, None)
        if old is not None:
            old.cancel()
        timer = threading.Timer(delay, _run_boot_schedule_sync, args=(db_path, device_id))
        timer.daemon = True
        _boot_schedule_sync_timers[device_id] = timer
        timer.start()
    print(
        f"[boot-sync] {device_id} online → SCHED_JSON in {delay:.0f}s",
        flush=True,
    )


def _cancel_boot_schedule_sync(device_id: str) -> None:
    with _boot_schedule_sync_lock:
        old = _boot_schedule_sync_timers.pop(device_id, None)
        if old is not None:
            old.cancel()


# 펌웨어 CH_KEY[] 순서와 동일 (CronusFarm.ino)
ALL_CHANNELS = [
    "led_a1",
    "led_a2",
    "led_b1",
    "pump_a1",
    "pump_a2",
    "pump_b1",
    "pump_b2",
    "fan_a1",
    "fan_a2",
    "fan_b1",
    "fan_b2",
    "pump_c1",
    "pump_c2",
    "pump_d1",
    "pump_d2",
    "led_b2",
]

_MANUAL_SWITCH_DDL = """
CREATE TABLE IF NOT EXISTS manual_switch_event (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL,
  ts_ms INTEGER NOT NULL,
  channel_key TEXT NOT NULL,
  source TEXT,
  prev_auto INTEGER,
  new_auto INTEGER,
  prev_state INTEGER,
  new_state INTEGER,
  meta_json TEXT,
  FOREIGN KEY (device_id) REFERENCES device(device_id)
);
CREATE INDEX IF NOT EXISTS idx_manual_dev_ts ON manual_switch_event(device_id, ts_ms DESC);
"""


def _ensure_manual_switch_event_table(conn: sqlite3.Connection) -> None:
    conn.executescript(_MANUAL_SWITCH_DDL)


def _insert_manual_switch_event(
    conn: sqlite3.Connection,
    *,
    device_id: str,
    channel_key: str,
    source: str,
    ts_ms: int,
    prev_auto: int,
    new_auto: int,
    prev_state: int,
    new_state: int,
    meta: dict[str, object],
) -> None:
    _ensure_manual_switch_event_table(conn)
    _ensure_device(conn, device_id)
    conn.execute(
        """INSERT INTO manual_switch_event
        (device_id, ts_ms, channel_key, source, prev_auto, new_auto, prev_state, new_state, meta_json)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            device_id,
            ts_ms,
            channel_key,
            source,
            prev_auto,
            new_auto,
            prev_state,
            new_state,
            json.dumps(meta, ensure_ascii=False),
        ),
    )


def _parse_kv(part: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for tok in (part or "").strip().split():
        if "=" in tok:
            k, _, v = tok.partition("=")
            out[k.strip()] = v.strip()
    return out


def _ensure_device(conn: sqlite3.Connection, device_id: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO device (device_id, label) VALUES (?, ?)",
        (device_id, device_id),
    )


def backfill_tele_channel_from_samples(
    conn: sqlite3.Connection,
    *,
    device_id: str,
    channel_key: str,
    cutoff_ms: int,
) -> int:
    """tele_sample raw를 다시 파싱해 tele_channel_fact에 없는 시각만 삽입."""
    cur = conn.cursor()
    cur.execute(
        """SELECT ts_ms, raw FROM tele_sample
        WHERE device_id=? AND ts_ms>=?
        ORDER BY ts_ms ASC
        LIMIT 12000""",
        (device_id, cutoff_ms),
    )
    inserted = 0
    for ts_ms, raw in cur.fetchall():
        if not raw:
            continue
        kv_s, kv_a, kv_t, _gu = parse_tele_sections(str(raw))
        if (
            channel_key not in kv_s
            and channel_key not in kv_a
            and channel_key not in kv_t
        ):
            continue
        st = kv_s.get(channel_key)
        au = kv_a.get(channel_key)
        state_i = int(st) if st in ("0", "1") else None
        auto_i = int(au) if au in ("0", "1") else None
        on_sec = off_sec = None
        tv = kv_t.get(channel_key)
        if tv and "/" in str(tv):
            a, _, b = str(tv).partition("/")
            if a.isdigit() and b.isdigit():
                on_sec, off_sec = int(a), int(b)
        if (
            state_i is None
            and auto_i is None
            and (on_sec is None or off_sec is None)
        ):
            continue
        tsm = int(ts_ms)
        cur.execute(
            """SELECT 1 FROM tele_channel_fact
            WHERE device_id=? AND channel_key=? AND ts_ms=?
            LIMIT 1""",
            (device_id, channel_key, tsm),
        )
        if cur.fetchone():
            continue
        cur.execute(
            """INSERT INTO tele_channel_fact
            (device_id, ts_ms, channel_key, state, auto_mode, on_sec, off_sec)
            VALUES (?,?,?,?,?,?,?)""",
            (device_id, tsm, channel_key, state_i, auto_i, on_sec, off_sec),
        )
        inserted += 1
    return inserted


def parse_tele_sections(raw: str) -> tuple[dict[str, str], dict[str, str], dict[str, str], list[tuple[str, str, int | None]]]:
    """Returns kvS, kvA, kvT(on/off strings), guard_events (channel, code, remain)."""
    kv_s: dict[str, str] = {}
    kv_a: dict[str, str] = {}
    kv_t: dict[str, str] = {}
    guards: list[tuple[str, str, int | None]] = []
    if not raw:
        return kv_s, kv_a, kv_t, guards
    for seg in raw.split("|"):
        seg = seg.strip()
        if seg.startswith("S:"):
            kv_s = _parse_kv(seg[2:])
        elif seg.startswith("A:"):
            kv_a = _parse_kv(seg[2:])
        elif seg.startswith("T:"):
            kv_t = _parse_kv(seg[2:])
        elif seg.startswith("G:"):
            rest = seg[2:].strip()
            if not rest or rest == "ok":
                continue
            for item in rest.split():
                if item == "ok":
                    continue
                if "=" not in item:
                    continue
                k, _, rhs = item.partition("=")
                k = k.strip()
                rhs = rhs.strip()
                if "/" in rhs:
                    code, _, num = rhs.partition("/")
                    remain = int(num) if num.isdigit() else None
                    guards.append((k, code.strip(), remain))
                else:
                    guards.append((k, rhs, None))
    return kv_s, kv_a, kv_t, guards


def _latest_tele_sample(
    cur: sqlite3.Cursor, device_id: str
) -> tuple[dict[str, str], dict[str, str], int | None]:
    """가장 최근 tele_sample → S/A 파싱 (모니터 타일·그래프 끝점 동기화)."""
    cur.execute(
        "SELECT ts_ms, raw FROM tele_sample WHERE device_id=? ORDER BY ts_ms DESC LIMIT 1",
        (device_id,),
    )
    row = cur.fetchone()
    if not row:
        return {}, {}, None
    ts_ms = int(row[0])
    kv_s, kv_a, _, _ = parse_tele_sections(str(row[1] or ""))
    return kv_s, kv_a, ts_ms


def _channel_display_mode(
    auto_mode: int | None, hold_expires_ms: int | None, now_ms: int
) -> str:
    """UI: tele A:0 → 수동, 유효 홀드 → 수동, 그 외 자동."""
    if hold_expires_ms is not None and int(hold_expires_ms) > now_ms:
        return "manual"
    if auto_mode is not None and int(auto_mode) == 0:
        return "manual"
    return "auto"


def _read_channel_holds(
    conn: sqlite3.Connection, device_id: str
) -> dict[str, tuple[int, int]]:
    _ensure_channel_manual_hold_table(conn)
    cur = conn.cursor()
    cur.execute(
        """SELECT channel_key, expires_ms, hold_minutes
        FROM channel_manual_hold WHERE device_id=?""",
        (device_id,),
    )
    return {str(r[0]): (int(r[1]), int(r[2])) for r in cur.fetchall()}


def _build_channel_status_live(
    conn: sqlite3.Connection,
    device_id: str,
    now_ms: int,
    *,
    upsert_facts: bool = False,
) -> dict[str, dict[str, object]]:
    """설정/침대 UI용 — 최신 tele_sample S(출력)·A(AUTO) 우선(모니터 타일과 동일)."""
    cur = conn.cursor()
    kv_s, kv_a, tele_ts = _latest_tele_sample(cur, device_id)
    holds = _read_channel_holds(conn, device_id)
    chans: dict[str, dict[str, object]] = {}
    for ch_key in ALL_CHANNELS:
        st_raw = kv_s.get(ch_key)
        au_raw = kv_a.get(ch_key)
        if st_raw not in ("0", "1") and au_raw not in ("0", "1"):
            continue
        state_i = int(st_raw) if st_raw in ("0", "1") else 0
        if au_raw in ("0", "1"):
            auto_i = int(au_raw)
        else:
            auto_i = 1
        ent: dict[str, object] = {
            "state": state_i,
            "auto_mode": auto_i,
            "ts_ms": tele_ts if tele_ts is not None else now_ms,
            "tele_ts_ms": tele_ts,
        }
        h = holds.get(ch_key)
        if h:
            ent["hold_expires_ms"] = h[0]
            ent["hold_minutes"] = h[1]
        ent["display_mode"] = _channel_display_mode(
            ent.get("auto_mode"), ent.get("hold_expires_ms"), now_ms
        )
        chans[ch_key] = ent
        if upsert_facts and tele_ts is not None:
            cur.execute(
                """SELECT state, auto_mode FROM tele_channel_fact
                WHERE device_id=? AND channel_key=? ORDER BY ts_ms DESC LIMIT 1""",
                (device_id, ch_key),
            )
            prev = cur.fetchone()
            if prev is None or int(prev[0]) != state_i or int(prev[1]) != auto_i:
                cur.execute(
                    """INSERT INTO tele_channel_fact
                    (device_id, ts_ms, channel_key, state, auto_mode, on_sec, off_sec)
                    VALUES (?,?,?,?,?,?,?)""",
                    (device_id, int(tele_ts), ch_key, state_i, auto_i, None, None),
                )
    if upsert_facts and chans:
        conn.commit()
    return chans


def parse_tele_rtc_local(raw: str) -> str | None:
    """tele `R:YYYYMMDDHHmmss` — Arduino RV3028 시각."""
    if not raw:
        return None
    for seg in raw.split("|"):
        seg = seg.strip()
        if seg.startswith("R:"):
            val = seg[2:].strip()
            digits = "".join(c for c in val if c.isdigit())
            if len(digits) >= 14:
                return digits[:14]
    return None


def _format_rtc14_display(rtc14: str | None) -> str | None:
    if not rtc14 or len(rtc14) < 14:
        return None
    return (
        f"{rtc14[0:4]}-{rtc14[4:6]}-{rtc14[6:8]} "
        f"{rtc14[8:10]}:{rtc14[10:12]}:{rtc14[12:14]}"
    )


def _query_r4_connectivity(cur: sqlite3.Cursor, device_id: str) -> dict[str, object]:
    """R4 MQTT 연결 — tele 수신 신선도(기본 90초)와 status retain."""
    from cf_time import now_ms

    pi_ts = now_ms()
    cur.execute(
        "SELECT ts_ms FROM tele_sample WHERE device_id=? ORDER BY ts_ms DESC LIMIT 1",
        (device_id,),
    )
    row = cur.fetchone()
    last_tele_ts_ms: int | None = int(row[0]) if row and row[0] is not None else None
    tele_stale_sec: int | None = None
    if last_tele_ts_ms is not None:
        tele_stale_sec = max(0, int((pi_ts - last_tele_ts_ms) / 1000))
    cur.execute(
        "SELECT payload FROM mqtt_status_log WHERE device_id=? ORDER BY ts_ms DESC LIMIT 1",
        (device_id,),
    )
    st_row = cur.fetchone()
    last_status: str | None = None
    if st_row and st_row[0] is not None:
        last_status = str(st_row[0]).strip().lower() or None
    # tele 1Hz 근처 — 90초 넘으면 offline 취급
    r4_online = tele_stale_sec is not None and tele_stale_sec <= 90
    return {
        "r4_online": r4_online,
        "last_status": last_status,
        "tele_stale_sec": tele_stale_sec,
        "last_tele_ts_ms": last_tele_ts_ms,
    }


def query_time_status(cur: sqlite3.Cursor, device_id: str) -> dict[str, object]:
    """Pi·tele·Arduino RTC 시각 비교."""
    from datetime import datetime

    from cf_time import (  # noqa: E402 — scripts/ 와 동일 디렉터리
        CRONUSFARM_TZ,
        format_local,
        kst_calendar_day_window_ms,
        now_kst,
        now_ms,
    )

    try:
        pi_dt = now_kst()
        pi_ts_ms = now_ms()
        pi_local_display = format_local(pi_ts_ms)
        pi_tz = CRONUSFARM_TZ
    except Exception:
        pi_dt = datetime.now()
        pi_ts_ms = int(time.time() * 1000)
        pi_local_display = time.strftime("%Y-%m-%d %H:%M:%S")
        pi_tz = ""

    cur.execute(
        "SELECT ts_ms, raw FROM tele_sample WHERE device_id=? ORDER BY ts_ms DESC LIMIT 1",
        (device_id,),
    )
    row = cur.fetchone()
    last_tele_ts_ms: int | None = None
    arduino_rtc_local: str | None = None
    if row:
        last_tele_ts_ms = int(row[0])
        arduino_rtc_local = parse_tele_rtc_local(str(row[1] or ""))

    arduino_skew_sec: int | None = None
    if arduino_rtc_local and len(arduino_rtc_local) >= 14:
        try:
            from datetime import datetime as dt

            ar_dt = dt.strptime(arduino_rtc_local[:14], "%Y%m%d%H%M%S")
            if pi_dt.tzinfo is not None:
                ar_dt = ar_dt.replace(tzinfo=pi_dt.tzinfo)
            arduino_skew_sec = int((ar_dt.timestamp() - pi_dt.timestamp()))
        except Exception:
            arduino_skew_sec = None

    day_anchor_ms, day_end_ms, _ = kst_calendar_day_window_ms(pi_ts_ms)
    conn_info = _query_r4_connectivity(cur, device_id)
    return {
        "device_id": device_id,
        "pi_ts_ms": pi_ts_ms,
        "pi_local_display": pi_local_display,
        "pi_tz": pi_tz,
        "day_anchor_ms": day_anchor_ms,
        "day_end_ms": day_end_ms,
        "last_tele_ts_ms": last_tele_ts_ms,
        "control_display": (
            format_local(last_tele_ts_ms) if last_tele_ts_ms else None
        ),
        "arduino_rtc_local": arduino_rtc_local,
        "arduino_rtc_display": _format_rtc14_display(arduino_rtc_local),
        "arduino_skew_sec": arduino_skew_sec,
        **conn_info,
    }


def kst_calendar_day_window_ms(now_ms: int | None = None) -> tuple[int, int, int]:
    """오늘 0:00~내일 0:00 KST (epoch ms). cf_time 단일 구현."""
    from cf_time import kst_calendar_day_window_ms as _kst_win

    return _kst_win(now_ms)


def query_channel_timeline(
    cur: sqlite3.Cursor,
    *,
    device_id: str,
    channel: str,
    hours: int,
) -> dict[str, object]:
    """채널 1개 24h 타임라인(호출 측에서 lock·cursor 보유)."""
    if hours < 1 or hours > 168:
        hours = 24
    now_ms = int(time.time() * 1000)
    # 24h UI 그래프: 달력 하루(KST 0~24)와 동일 창. 그 외는 rolling N시간.
    if hours == 24:
        anchor_ts_ms, day_end_ms, now_ms = kst_calendar_day_window_ms(now_ms)
        cutoff = anchor_ts_ms
        window_day_end_ms = day_end_ms
    else:
        cutoff = now_ms - hours * 3600 * 1000
        anchor_ts_ms = cutoff
        window_day_end_ms = None
    cur.execute(
        """SELECT ts_ms, state, auto_mode
        FROM tele_channel_fact
        WHERE device_id=? AND channel_key=? AND ts_ms >= ?
        ORDER BY ts_ms ASC
        LIMIT 4000""",
        (device_id, channel, cutoff),
    )
    points: list[dict[str, object]] = [
        {"ts_ms": int(r[0]), "state": r[1], "auto_mode": r[2]}
        for r in cur.fetchall()
    ]
    cur.execute(
        """SELECT ts_ms, state, auto_mode
        FROM tele_channel_fact
        WHERE device_id=? AND channel_key=? AND ts_ms < ?
        ORDER BY ts_ms DESC
        LIMIT 1""",
        (device_id, channel, cutoff),
    )
    pre = cur.fetchone()
    if pre is not None:
        points.insert(
            0,
            {"ts_ms": anchor_ts_ms, "state": pre[1], "auto_mode": pre[2]},
        )
    elif points:
        points.insert(
            0,
            {
                "ts_ms": anchor_ts_ms,
                "state": points[0]["state"],
                "auto_mode": points[0].get("auto_mode"),
            },
        )
    cur.execute(
        """SELECT ts_ms, state, auto_mode FROM tele_channel_fact
        WHERE device_id=? AND channel_key=? ORDER BY ts_ms DESC LIMIT 1""",
        (device_id, channel),
    )
    latest_row = cur.fetchone()
    kv_live, kv_a_live, tele_ts = _latest_tele_sample(cur, device_id)
    st_live_raw = kv_live.get(channel)
    st_live = int(st_live_raw) if st_live_raw in ("0", "1") else None
    au_live_raw = kv_a_live.get(channel)
    au_live = int(au_live_raw) if au_live_raw in ("0", "1") else None
    if latest_row is not None:
        st_now = latest_row[1]
        au_now = latest_row[2]
        # 그래프 오른쪽 끝 = 최신 tele(타일과 동일). fact가 오래된 ON이면 덮어씀.
        if st_live is not None:
            st_now = st_live
            if au_live is not None:
                au_now = au_live
        if points and int(points[-1]["ts_ms"]) >= now_ms - 5000:
            points[-1] = {
                "ts_ms": now_ms,
                "state": st_now,
                "auto_mode": au_now,
            }
        else:
            points.append(
                {"ts_ms": now_ms, "state": st_now, "auto_mode": au_now}
            )
    elif st_live is not None:
        points.append(
            {
                "ts_ms": now_ms,
                "state": st_live,
                "auto_mode": au_live,
            }
        )
    elif points:
        last = points[-1]
        last_ts = int(last["ts_ms"])
        if last_ts < now_ms:
            points.append(
                {
                    "ts_ms": now_ms,
                    "state": last["state"],
                    "auto_mode": last.get("auto_mode"),
                }
            )
    live_at_now: dict[str, object] | None = None
    if st_live is not None:
        live_at_now = {
            "state": st_live,
            "auto_mode": au_live,
            "tele_ts_ms": tele_ts,
        }
    if window_day_end_ms is not None:
        points = [p for p in points if int(p["ts_ms"]) <= now_ms]
    day_end = int(window_day_end_ms) if window_day_end_ms is not None else None
    return {
        "device_id": device_id,
        "channel_key": channel,
        "hours": hours,
        "anchor_ts_ms": anchor_ts_ms,
        "window_end_ms": now_ms,
        "window_day_end_ms": window_day_end_ms,
        "chart_now_ms": now_ms,
        "tz": "Asia/Seoul",
        "live_at_now": live_at_now,
        "points": points,
        "day_window": (
            {
                "anchor_ts_ms": int(anchor_ts_ms),
                "day_end_ms": day_end,
                "chart_now_ms": now_ms,
                "tz": "Asia/Seoul",
            }
            if day_end is not None
            else None
        ),
    }


def handle_bridge(conn: sqlite3.Connection, db_path: Path, lock: threading.Lock) -> type[BaseHTTPRequestHandler]:
    # tele S: 구간에서 state 전이 추적(자동 모드일 때만 감사 로그)
    last_tele_ch: dict[tuple[str, str], tuple[int | None, int]] = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            return

        def _cors_headers(self) -> None:
            o = self.headers.get("Origin")
            if o:
                self.send_header("Access-Control-Allow-Origin", o)
                self.send_header("Vary", "Origin")
            else:
                self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header(
                "Access-Control-Allow-Methods", "GET, PUT, POST, DELETE, OPTIONS"
            )
            self.send_header(
                "Access-Control-Allow-Headers",
                "Content-Type, X-Forwarded-Email, X-Auth-Request-Email",
            )

        def _write_json(self, code: int, body: object) -> None:
            raw = (
                json.dumps(body, ensure_ascii=False).encode("utf-8")
                if isinstance(body, dict)
                else str(body).encode("utf-8")
            )
            self.send_response(code)
            self._cors_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _admin_get(self, path: str, qs: dict) -> bool:
            if not path.startswith("/api/admin/"):
                return False
            try:
                from cronusfarm_admin_api import handle_admin_get

                with lock:
                    status, payload = handle_admin_get(conn, path, qs, self.headers)
                if status == 404:
                    self.send_error(404)
                    return True
                self._write_json(status, payload)
                return True
            except Exception as e:
                self._write_json(500, {"ok": False, "error": str(e)})
                return True

        def _json_body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length)
            if not raw:
                return {}
            try:
                return json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                return {}

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self._cors_headers()
            self.end_headers()

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            qs = parse_qs(parsed.query or "")
            if self._admin_get(path, qs):
                return
            if path == "/health":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")
                return
            if path == "/api/schedule/batch":
                qs = parse_qs(parsed.query or "")
                device_id = (qs.get("device_id") or ["cronusfarm-01"])[0].strip() or "cronusfarm-01"
                with lock:
                    _ensure_schedule_rule_table(conn)
                    cur = conn.cursor()
                    _ensure_device(conn, device_id)
                    by_ch = _fetch_schedule_rules_by_channel(cur, device_id)
                channels_body = {
                    ch: {"channel_key": ch, "rules": rules, "rule_count": len(rules)}
                    for ch, rules in by_ch.items()
                }
                body = {"device_id": device_id, "channels": channels_body}
                raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self._cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return

            if path == "/api/schedule":
                qs = parse_qs(parsed.query or "")
                device_id = (qs.get("device_id") or [""])[0].strip()
                channel = (qs.get("channel") or [""])[0].strip()
                if not device_id or not channel:
                    self.send_response(400)
                    self._cors_headers()
                    self.end_headers()
                    self.wfile.write(b"device_id and channel required")
                    return
                with lock:
                    _ensure_schedule_rule_table(conn)
                    cur = conn.cursor()
                    _ensure_device(conn, device_id)
                    cur.execute(
                        """SELECT id, dow_mask, slot_index, on_min, off_min, enabled, updated_at,
                        COALESCE(rule_kind, 'window'), on_sec, off_sec
                        FROM schedule_rule
                        WHERE device_id=? AND channel_key=?
                        ORDER BY slot_index, id""",
                        (device_id, channel),
                    )
                    rules = [_schedule_rule_entry_from_row(r) for r in cur.fetchall()]
                body = {
                    "device_id": device_id,
                    "channel_key": channel,
                    "rules": rules,
                    "rule_count": len(rules),
                }
                raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self._cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return

            if path == "/api/time/now":
                from cf_time import query_time_now

                body = query_time_now()
                raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self._cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return

            if path == "/api/time/status":
                qs = parse_qs(parsed.query or "")
                device_id = (qs.get("device_id") or ["cronusfarm-01"])[0].strip() or "cronusfarm-01"
                with lock:
                    cur = conn.cursor()
                    body = query_time_status(cur, device_id)
                raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self._cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return

            if path == "/api/schedule/sync_device":
                qs = parse_qs(parsed.query or "")
                device_id = (qs.get("device_id") or ["cronusfarm-01"])[0].strip() or "cronusfarm-01"
                with lock:
                    _ensure_schedule_rule_table(conn)
                    _ensure_device(conn, device_id)
                    n, auto_n = _sync_device_schedules_mqtt_full(
                        conn, db_path, lock, device_id
                    )
                body = {
                    "ok": True,
                    "device_id": device_id,
                    "channels_published": n,
                    "auto_published": auto_n,
                }
                raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self._cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return

            if path == "/api/device/force_all_auto":
                qs = parse_qs(parsed.query or "")
                device_id = (qs.get("device_id") or ["cronusfarm-01"])[0].strip() or "cronusfarm-01"
                try:
                    out = force_device_all_auto(db_path, lock, device_id)
                    out["ok"] = True
                    raw = json.dumps(out, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self._cors_headers()
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except Exception as e:
                    err = json.dumps(
                        {"ok": False, "error": str(e)}, ensure_ascii=False
                    ).encode("utf-8")
                    self.send_response(500)
                    self._cors_headers()
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(err)))
                    self.end_headers()
                    self.wfile.write(err)
                return

            if path == "/api/device/force_all_on":
                qs = parse_qs(parsed.query or "")
                device_id = (qs.get("device_id") or ["cronusfarm-01"])[0].strip() or "cronusfarm-01"
                try:
                    out = force_device_all_manual_on(db_path, lock, device_id)
                    out["ok"] = True
                    raw = json.dumps(out, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self._cors_headers()
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except Exception as e:
                    err = json.dumps(
                        {"ok": False, "error": str(e)}, ensure_ascii=False
                    ).encode("utf-8")
                    self.send_response(500)
                    self._cors_headers()
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(err)))
                    self.end_headers()
                    self.wfile.write(err)
                return

            if path == "/api/sensor/series":
                qs = parse_qs(parsed.query or "")
                device_id = (qs.get("device_id") or ["cronusfarm-01"])[0].strip() or "cronusfarm-01"
                zone = (qs.get("zone") or ["phw3988"])[0].strip() or "phw3988"
                hours = int((qs.get("hours") or ["24"])[0] or 24)
                if hours < 1 or hours > 168:
                    hours = 24
                cutoff = int(time.time() * 1000) - hours * 3600 * 1000
                with lock:
                    cur = conn.cursor()
                    cur.execute(
                        """SELECT ts_ms, ph, ec, temp_c FROM sensor_reading
                        WHERE device_id=? AND zone=? AND ts_ms >= ? ORDER BY ts_ms ASC LIMIT 5000""",
                        (device_id, zone, cutoff),
                    )
                    pts = [
                        {
                            "ts_ms": int(r[0]),
                            "ph": r[1],
                            "ec": r[2],
                            "temp_c": r[3],
                        }
                        for r in cur.fetchall()
                    ]
                body = {
                    "ok": True,
                    "device_id": device_id,
                    "zone": zone,
                    "hours": hours,
                    "points": pts,
                }
                raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self._cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return

            if path == "/api/sensor/latest":
                qs = parse_qs(parsed.query or "")
                device_id = (qs.get("device_id") or ["cronusfarm-01"])[0].strip()
                zone = (qs.get("zone") or ["phw3988"])[0].strip()
                with lock:
                    _ensure_device(conn, device_id)
                    cur = conn.cursor()
                    cur.execute(
                        """SELECT ts_ms, zone, ph, ec, temp_c, humidity_pct, light_lux, co2_ppm, source, raw_json
                        FROM sensor_reading
                        WHERE device_id=? AND zone=?
                        ORDER BY ts_ms DESC LIMIT 1""",
                        (device_id, zone),
                    )
                    row = cur.fetchone()
                if not row:
                    body = {"ok": False, "device_id": device_id, "zone": zone}
                    code = 404
                else:
                    body = {
                        "ok": True,
                        "device_id": device_id,
                        "zone": row[1],
                        "ts_ms": int(row[0]),
                        "ph": row[2],
                        "ec": row[3],
                        "temp_c": row[4],
                        "humidity_pct": row[5],
                        "light_lux": row[6],
                        "co2_ppm": row[7],
                        "source": row[8],
                        "raw_json": row[9],
                    }
                    code = 200
                raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self._cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            if path == "/api/audit_log":
                qs = parse_qs(parsed.query or "")
                device_id = (qs.get("device_id") or [""])[0].strip()
                if not device_id:
                    self.send_response(400)
                    self._cors_headers()
                    self.end_headers()
                    self.wfile.write(b"device_id required")
                    return
                try:
                    limit = int((qs.get("limit") or ["80"])[0] or 80)
                except ValueError:
                    limit = 80
                limit = max(1, min(500, limit))
                ch_f = (qs.get("channel") or [""])[0].strip()
                try:
                    since_ms = int((qs.get("since_ms") or ["0"])[0] or 0)
                except ValueError:
                    since_ms = 0
                with lock:
                    _ensure_manual_switch_event_table(conn)
                    cur = conn.cursor()
                    if ch_f:
                        cur.execute(
                            """SELECT id, ts_ms, channel_key, source, prev_auto, new_auto,
                            prev_state, new_state, meta_json
                            FROM manual_switch_event
                            WHERE device_id=? AND channel_key=? AND ts_ms >= ?
                            ORDER BY ts_ms DESC LIMIT ?""",
                            (device_id, ch_f, since_ms, limit),
                        )
                    else:
                        cur.execute(
                            """SELECT id, ts_ms, channel_key, source, prev_auto, new_auto,
                            prev_state, new_state, meta_json
                            FROM manual_switch_event
                            WHERE device_id=? AND ts_ms >= ?
                            ORDER BY ts_ms DESC LIMIT ?""",
                            (device_id, since_ms, limit),
                        )
                    rows_out: list[dict[str, object]] = []
                    for r in cur.fetchall():
                        meta_obj: object = r[8]
                        try:
                            if isinstance(r[8], str) and r[8]:
                                meta_obj = json.loads(r[8])
                        except json.JSONDecodeError:
                            meta_obj = r[8]
                        rows_out.append(
                            {
                                "id": int(r[0]),
                                "ts_ms": int(r[1]),
                                "channel_key": r[2],
                                "source": r[3],
                                "prev_auto": r[4],
                                "new_auto": r[5],
                                "prev_state": r[6],
                                "new_state": r[7],
                                "meta": meta_obj,
                            }
                        )
                body = {"device_id": device_id, "limit": limit, "rows": rows_out}
                raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self._cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            if path == "/api/channel/timeline/batch":
                qs = parse_qs(parsed.query or "")
                device_id = (qs.get("device_id") or [""])[0].strip()
                ch_raw = (qs.get("channels") or [""])[0].strip()
                hours = int((qs.get("hours") or ["24"])[0] or 24)
                if not device_id or not ch_raw:
                    self.send_response(400)
                    self._cors_headers()
                    self.end_headers()
                    self.wfile.write(b"device_id and channels required")
                    return
                channels = [
                    c.strip()
                    for c in ch_raw.split(",")
                    if c.strip()
                ][:32]
                if not channels:
                    self.send_response(400)
                    self._cors_headers()
                    self.end_headers()
                    self.wfile.write(b"channels empty")
                    return
                # 채널·시간이 많으면 단일 lock 장시간 점유 → /ui·status 타임아웃
                if hours > 12 and len(channels) > 6:
                    hours = 12
                if len(channels) > 12:
                    channels = channels[:12]
                if not _timeline_batch_slots.acquire(timeout=2.0):
                    self.send_response(503)
                    self._cors_headers()
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(
                        b'{"error":"timeline_batch_busy","retry_sec":3}'
                    )
                    return
                ch_map: dict[str, object] = {}
                try:
                    rconn = _open_sqlite_read(db_path)
                    try:
                        cur = rconn.cursor()
                        for ch in channels:
                            ch_map[ch] = query_channel_timeline(
                                cur,
                                device_id=device_id,
                                channel=ch,
                                hours=hours,
                            )
                    finally:
                        rconn.close()
                finally:
                    _timeline_batch_slots.release()
                day_window: dict[str, object] | None = None
                if hours == 24 and ch_map:
                    first = next(iter(ch_map.values()))
                    a = first.get("anchor_ts_ms")
                    d = first.get("window_day_end_ms")
                    n = first.get("window_end_ms")
                    if a is not None and d is not None:
                        day_window = {
                            "anchor_ts_ms": int(a),
                            "day_end_ms": int(d),
                            "chart_now_ms": int(n) if n is not None else int(time.time() * 1000),
                            "tz": "Asia/Seoul",
                        }
                body = {
                    "device_id": device_id,
                    "hours": hours,
                    "day_window": day_window,
                    "channels": ch_map,
                }
                raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self._cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            if path == "/api/channel/timeline":
                qs = parse_qs(parsed.query or "")
                device_id = (qs.get("device_id") or [""])[0].strip()
                channel = (qs.get("channel") or [""])[0].strip()
                hours = int((qs.get("hours") or ["24"])[0] or 24)
                if not device_id or not channel:
                    self.send_response(400)
                    self._cors_headers()
                    self.end_headers()
                    self.wfile.write(b"device_id and channel required")
                    return
                with lock:
                    cur = conn.cursor()
                    body = query_channel_timeline(
                        cur, device_id=device_id, channel=channel, hours=hours
                    )
                raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self._cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            if path == "/api/channel/status":
                qs = parse_qs(parsed.query or "")
                device_id = (qs.get("device_id") or ["cronusfarm-01"])[0].strip() or "cronusfarm-01"
                now_ms = int(time.time() * 1000)
                rconn = _open_sqlite_read(db_path)
                try:
                    chans = _build_channel_status_live(
                        rconn, device_id, now_ms, upsert_facts=False
                    )
                finally:
                    rconn.close()
                body = {"device_id": device_id, "channels": chans}
                raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self._cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            if path == "/api/snapshot":
                qs = parse_qs(parsed.query or "")
                device_id = (qs.get("device_id") or ["cronusfarm-01"])[0].strip() or "cronusfarm-01"
                with lock:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT COUNT(*) FROM tele_sample WHERE device_id=?",
                        (device_id,),
                    )
                    tele_n = int(cur.fetchone()[0])
                    cur.execute(
                        "SELECT COUNT(*) FROM mqtt_cmd_log WHERE device_id=?",
                        (device_id,),
                    )
                    cmd_n = int(cur.fetchone()[0])
                    cur.execute(
                        "SELECT MAX(ts_ms) FROM tele_sample WHERE device_id=?",
                        (device_id,),
                    )
                    row = cur.fetchone()
                    last_tele_ts_ms = int(row[0]) if row and row[0] is not None else None
                    cur.execute(
                        "SELECT key, value, updated_at FROM settings_kv WHERE device_id=? ORDER BY key",
                        (device_id,),
                    )
                    kv_rows = [
                        {"key": r[0], "value": r[1], "updated_at": r[2]}
                        for r in cur.fetchall()
                    ]
                body = {
                    "device_id": device_id,
                    "bridge": "ok",
                    "db_path": str(db_path),
                    "tele_sample_count": tele_n,
                    "mqtt_cmd_count": cmd_n,
                    "last_tele_ts_ms": last_tele_ts_ms,
                    "settings_kv": kv_rows,
                }
                raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            self.send_error(404)

        def do_DELETE(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            if not path.startswith("/api/admin/"):
                self.send_error(404)
                return
            try:
                from cronusfarm_admin_api import handle_admin_delete

                qs = parse_qs(parsed.query or "")
                with lock:
                        status, payload = handle_admin_delete(
                            conn, path, qs, self.headers
                        )
                if status == 404:
                    self.send_error(404)
                    return
                self._write_json(status, payload)
            except Exception as e:
                self._write_json(500, {"ok": False, "error": str(e)})

        def do_PUT(self) -> None:
            parsed = urlparse(self.path)
            apath = parsed.path
            if apath.startswith("/api/admin/"):
                try:
                    from cronusfarm_admin_api import handle_admin_put

                    body = self._json_body()
                    with lock:
                        status, payload = handle_admin_put(
                            conn, apath, body, self.headers
                        )
                    if status == 404:
                        self.send_error(404)
                        return
                    self._write_json(status, payload)
                    return
                except Exception as e:
                    self._write_json(500, {"ok": False, "error": str(e)})
                    return
            if apath != "/api/schedule":
                self.send_error(404)
                return
            qs = parse_qs(parsed.query or "")
            device_id = (qs.get("device_id") or [""])[0].strip()
            channel = (qs.get("channel") or [""])[0].strip()
            if not device_id or not channel:
                self.send_response(400)
                self._cors_headers()
                self.end_headers()
                self.wfile.write(b"device_id and channel required")
                return
            body = self._json_body()
            rules_in = body.get("rules")
            if not isinstance(rules_in, list):
                self.send_response(400)
                self._cors_headers()
                self.end_headers()
                self.wfile.write(b'{"error":"rules array required"}')
                return
            try:
                mqtt_rules: list[dict[str, object]] = []
                with lock:
                    _ensure_schedule_rule_table(conn)
                    _ensure_device(conn, device_id)
                    c = conn.cursor()
                    c.execute(
                        "DELETE FROM schedule_rule WHERE device_id=? AND channel_key=?",
                        (device_id, channel),
                    )
                    for i, row in enumerate(rules_in):
                        if not isinstance(row, dict):
                            continue
                        dow = int(row.get("dow_mask", 127))
                        slot = int(row.get("slot_index", i))
                        en = int(row.get("enabled", 1))
                        rk = str(row.get("rule_kind") or "window").strip().lower()
                        if rk not in ("window", "cycle"):
                            rk = "window"
                        if dow < 0 or dow > 127:
                            raise ValueError("dow_mask 0..127")
                        if rk == "cycle":
                            on_m = int(row.get("on_min", 0))
                            off_m = int(row.get("off_min", 0))
                            on_sec = int(row.get("on_sec", 0))
                            off_sec = int(row.get("off_sec", 0))
                            if on_m < 0 or on_m > 1440 or off_m < 0 or off_m > 1440:
                                raise ValueError("cycle: on_min/off_min 0..1440")
                            if on_sec < 0 or off_sec < 0:
                                raise ValueError("cycle: on_sec/off_sec 0 이상")
                            if on_sec + off_sec == 0:
                                raise ValueError("cycle: 켜짐·꺼짐 길이 합이 0이면 안 됩니다")
                            if on_sec > 86400 or off_sec > 86400:
                                raise ValueError("cycle: on_sec/off_sec 86400 이하")
                            rec = {
                                "rule_kind": "cycle",
                                "dow_mask": dow,
                                "slot_index": slot,
                                "on_min": on_m,
                                "off_min": off_m,
                                "on_sec": on_sec,
                                "off_sec": off_sec,
                                "enabled": 1 if en else 0,
                            }
                            mqtt_rules.append(rec)
                            c.execute(
                                """INSERT INTO schedule_rule
                                (device_id, channel_key, dow_mask, slot_index, on_min, off_min, enabled, rule_kind, on_sec, off_sec, updated_at)
                                VALUES (?,?,?,?,?,?,?,?,?,?, datetime('now'))""",
                                (
                                    device_id,
                                    channel,
                                    dow,
                                    slot,
                                    on_m,
                                    off_m,
                                    1 if en else 0,
                                    "cycle",
                                    on_sec,
                                    off_sec,
                                ),
                            )
                        else:
                            on_m = int(row.get("on_min", 0))
                            off_m = int(row.get("off_min", 0))
                            if on_m < 0 or on_m > 1440 or off_m < 0 or off_m > 1440:
                                raise ValueError("on_min/off_min 0..1440")
                            rec = {
                                "rule_kind": "window",
                                "dow_mask": dow,
                                "slot_index": slot,
                                "on_min": on_m,
                                "off_min": off_m,
                                "on_sec": None,
                                "off_sec": None,
                                "enabled": 1 if en else 0,
                            }
                            mqtt_rules.append(rec)
                            c.execute(
                                """INSERT INTO schedule_rule
                                (device_id, channel_key, dow_mask, slot_index, on_min, off_min, enabled, rule_kind, on_sec, off_sec, updated_at)
                                VALUES (?,?,?,?,?,?,?,?,?,?, datetime('now'))""",
                                (
                                    device_id,
                                    channel,
                                    dow,
                                    slot,
                                    on_m,
                                    off_m,
                                    1 if en else 0,
                                    "window",
                                    None,
                                    None,
                                ),
                            )
                    conn.commit()
                mqtt_st, sch_ver = _publish_schedule_mqtt(
                    device_id=device_id,
                    channel_key=channel,
                    rules=mqtt_rules,
                )
                with lock:
                    _insert_manual_switch_event(
                        conn,
                        device_id=device_id,
                        channel_key=channel,
                        source="schedule",
                        ts_ms=int(time.time() * 1000),
                        prev_auto=-1,
                        new_auto=-1,
                        prev_state=-1,
                        new_state=-1,
                        meta={
                            "action": "schedule_save",
                            "saved": len(mqtt_rules),
                            "sch_ver": sch_ver,
                            "mqtt": mqtt_st,
                        },
                    )
                    conn.commit()
                out = {
                    "ok": True,
                    "saved": len(mqtt_rules),
                    "sch_ver": sch_ver,
                    "mqtt": mqtt_st,
                }
                raw = json.dumps(out, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self._cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            except Exception as e:
                with lock:
                    conn.rollback()
                err = json.dumps(
                    {"ok": False, "error": str(e)}, ensure_ascii=False
                ).encode("utf-8")
                self.send_response(400)
                self._cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(err)))
                self.end_headers()
                self.wfile.write(err)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            body = self._json_body()
            if path.startswith("/api/admin/"):
                try:
                    from cronusfarm_admin_api import handle_admin_post

                    with lock:
                        status, payload = handle_admin_post(
                            conn, path, body, self.headers
                        )
                    if status == 404:
                        self.send_error(404)
                        return
                    self._write_json(status, payload)
                    return
                except Exception as e:
                    self._write_json(500, {"ok": False, "error": str(e)})
                    return
            if path == "/api/channel-action":
                try:
                    device_id = str(body.get("device_id") or "cronusfarm-01").strip()
                    channel_key = str(
                        body.get("channel_key") or body.get("channel") or ""
                    ).strip()
                    action = str(body.get("action") or "").strip()
                    if not channel_key:
                        raise ValueError("channel required")
                    if not action:
                        raise ValueError("action required")
                    mqtt_parts = _channel_action_mqtt_parts(channel_key, action, body)
                    mqtt_st = "skipped"
                    if mqtt_parts:
                        mqtt_st = _mqtt_publish_cmd(
                            device_id, " ".join(mqtt_parts)
                        )
                    hold_exp_ms: int | None = None
                    with lock:
                        _ensure_device(conn, device_id)
                        body_log = dict(body)
                        body_log.setdefault("source", "ui")
                        body_log["mqtt_payload"] = (
                            " ".join(mqtt_parts) if mqtt_parts else None
                        )
                        self._post_manual_event(conn, body_log)
                        if action == "set_auto":
                            _cancel_hold_revert(device_id, channel_key)
                            _delete_channel_hold(conn, device_id, channel_key)
                        elif action in ("set_manual", "set_output"):
                            hm_raw = body.get("hold_minutes")
                            if hm_raw is None:
                                hm_raw = _read_channel_hold_minutes(
                                    conn, device_id, channel_key
                                )
                            hm = _normalize_hold_minutes(hm_raw)
                            hold_exp_ms = _upsert_channel_hold(
                                conn, device_id, channel_key, hm
                            )
                        conn.commit()
                    if hold_exp_ms is not None:
                        _arm_hold_timer_at_expiry(
                            db_path, lock, device_id, channel_key, hold_exp_ms
                        )
                    out = {
                        "ok": True,
                        "mqtt": mqtt_st,
                        "cmd": " ".join(mqtt_parts) if mqtt_parts else "",
                    }
                    raw = json.dumps(out, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self._cors_headers()
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except Exception as e:
                    err = json.dumps(
                        {"ok": False, "error": str(e)}, ensure_ascii=False
                    ).encode("utf-8")
                    self.send_response(400)
                    self._cors_headers()
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(err)))
                    self.end_headers()
                    self.wfile.write(err)
                return
            if path == "/api/device/ensure_auto_mode":
                try:
                    device_id = str(
                        body.get("device_id") or "cronusfarm-01"
                    ).strip() or "cronusfarm-01"
                    out = _ensure_auto_mode_unless_hold(db_path, lock, device_id)
                    raw = json.dumps(out, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self._cors_headers()
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except Exception as e:
                    err = json.dumps(
                        {"ok": False, "error": str(e)}, ensure_ascii=False
                    ).encode("utf-8")
                    self.send_response(400)
                    self._cors_headers()
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(err)))
                    self.end_headers()
                    self.wfile.write(err)
                return
            if path == "/api/rtc/sync_to_device":
                try:
                    device_id = str(
                        body.get("device_id") or "cronusfarm-01"
                    ).strip() or "cronusfarm-01"
                    rtc14 = time.strftime("%Y%m%d%H%M%S", time.localtime())
                    payload = f"rtc_local={rtc14}"
                    mqtt_st = _mqtt_publish_cmd(device_id, payload)
                    with lock:
                        cur = conn.cursor()
                        conn_info = _query_r4_connectivity(cur, device_id)
                    warning: str | None = None
                    if mqtt_st != "published":
                        warning = (
                            f"MQTT cmd 발행 실패({mqtt_st}). "
                            "Pi에 mosquitto-clients·브로커 상태를 확인하세요."
                        )
                    elif not conn_info.get("r4_online"):
                        stale = conn_info.get("tele_stale_sec")
                        stale_txt = (
                            f"tele {stale}초 전"
                            if stale is not None
                            else "tele 없음"
                        )
                        warning = (
                            f"R4가 MQTT offline({stale_txt}). "
                            "rtc_local은 브로커에만 전달되었고 Arduino는 수신하지 못했습니다. "
                            "R4 WiFi·전원·리셋 후 다시 시도하세요."
                        )
                    out = {
                        "ok": True,
                        "device_id": device_id,
                        "rtc_local": rtc14,
                        "mqtt": mqtt_st,
                        "warning": warning,
                        **conn_info,
                    }
                    raw = json.dumps(out, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self._cors_headers()
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except Exception as e:
                    err = json.dumps(
                        {"ok": False, "error": str(e)}, ensure_ascii=False
                    ).encode("utf-8")
                    self.send_response(400)
                    self._cors_headers()
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(err)))
                    self.end_headers()
                    self.wfile.write(err)
                return
            if path == "/api/schedule/seed_defaults":
                try:
                    from cronusfarm_schedule_defaults import (
                        DEFAULT_DEVICE_ID,
                        apply_default_schedules_to_db,
                    )

                    device_id = str(
                        body.get("device_id") or DEFAULT_DEVICE_ID
                    ).strip() or DEFAULT_DEVICE_ID
                    force = bool(body.get("force"))
                    with lock:
                        _ensure_schedule_rule_table(conn)
                        result = apply_default_schedules_to_db(
                            conn, device_id, force=force
                        )
                        n_pub = 0
                        auto_pub = 0
                        if not result.get("skipped"):
                            n_pub, auto_pub = _sync_device_schedules_mqtt_full(
                                conn, db_path, lock, device_id
                            )
                    out = {
                        "ok": True,
                        "device_id": device_id,
                        "force": force,
                        **result,
                        "channels_published": n_pub,
                        "auto_published": auto_pub,
                    }
                    raw = json.dumps(out, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self._cors_headers()
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except Exception as e:
                    err = json.dumps(
                        {"ok": False, "error": str(e)}, ensure_ascii=False
                    ).encode("utf-8")
                    self.send_response(400)
                    self._cors_headers()
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(err)))
                    self.end_headers()
                    self.wfile.write(err)
                return
            if path == "/api/channel/backfill":
                try:
                    device_id = str(body.get("device_id") or "cronusfarm-01").strip()
                    ch = str(
                        body.get("channel_key") or body.get("channel") or ""
                    ).strip()
                    if not ch:
                        raise ValueError("channel or channel_key required")
                    hours = int(body.get("hours") or 72)
                    if hours < 1 or hours > 168:
                        hours = 72
                    cutoff = int(time.time() * 1000) - hours * 3600 * 1000
                    with lock:
                        _ensure_device(conn, device_id)
                        n_ins = backfill_tele_channel_from_samples(
                            conn,
                            device_id=device_id,
                            channel_key=ch,
                            cutoff_ms=cutoff,
                        )
                        conn.commit()
                    out = {
                        "ok": True,
                        "device_id": device_id,
                        "channel_key": ch,
                        "hours": hours,
                        "inserted": n_ins,
                    }
                    raw = json.dumps(out, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self._cors_headers()
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except Exception as e:
                    err = json.dumps(
                        {"ok": False, "error": str(e)}, ensure_ascii=False
                    ).encode("utf-8")
                    self.send_response(400)
                    self._cors_headers()
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(err)))
                    self.end_headers()
                    self.wfile.write(err)
                return
            try:
                panel_holds: list[tuple[str, str, int]] = []
                tg_register_out: dict | None = None
                tele_republish: tuple[str, str, str] | None = None
                with lock:
                    if path == "/ingest/tele":
                        panel_holds = self._post_tele(conn, body)
                        tele_republish = (
                            str(body.get("device_id") or "cronusfarm-01").strip(),
                            str(body.get("raw") or ""),
                            str(body.get("topic") or ""),
                        )
                    elif path == "/ingest/cmd":
                        self._post_cmd(conn, body)
                    elif path == "/ingest/status":
                        self._post_status(conn, body)
                    elif path == "/settings/kv":
                        self._post_kv(conn, body)
                    elif path == "/ingest/manual_event":
                        self._post_manual_event(conn, body)
                    elif path == "/ingest/sensor":
                        self._post_sensor(conn, body)
                    elif path == "/ingest/telegram-register":
                        from cronusfarm_admin_api import register_telegram_application

                        tg_register_out = register_telegram_application(
                            conn,
                            str(body.get("chat_id") or ""),
                            str(body.get("display_name") or ""),
                            str(body.get("telegram_username") or ""),
                        )
                    else:
                        self.send_error(404)
                        return
                    conn.commit()
                if path == "/ingest/telegram-register":
                    self._write_json(200, tg_register_out or {"ok": False})
                    return
                if path == "/ingest/tele":
                    for dev, ch, exp_ms in panel_holds:
                        _arm_hold_timer_at_expiry(db_path, lock, dev, ch, int(exp_ms))
                    if tele_republish:
                        _mqtt_republish_tele(
                            tele_republish[0],
                            tele_republish[1],
                            tele_republish[2],
                        )
                self.send_response(204)
                self.end_headers()
            except Exception as e:
                with lock:
                    conn.rollback()
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode("utf-8"))

        def _post_tele(
            self, c: sqlite3.Connection, body: dict
        ) -> list[tuple[str, str, int]]:
            device_id = str(body.get("device_id") or "cronusfarm-01").strip()
            raw = str(body.get("raw") or "")
            topic = str(body.get("topic") or "")
            ts_ms = int(body.get("ts_ms") or (time.time() * 1000))
            _ensure_device(c, device_id)
            c.execute(
                "INSERT INTO tele_sample (device_id, ts_ms, topic, raw) VALUES (?,?,?,?)",
                (device_id, ts_ms, topic, raw),
            )
            kv_s, kv_a, kv_t, guards = parse_tele_sections(raw)
            panel_holds: list[tuple[str, str, int]] = []
            for ch in ALL_CHANNELS:
                st = kv_s.get(ch)
                au = kv_a.get(ch)
                if st is None and au is None and ch not in kv_t:
                    continue
                state_i = int(st) if st in ("0", "1") else None
                auto_i = int(au) if au in ("0", "1") else None
                on_sec = off_sec = None
                tv = kv_t.get(ch)
                if tv and "/" in str(tv):
                    a, _, b = str(tv).partition("/")
                    if a.isdigit() and b.isdigit():
                        on_sec, off_sec = int(a), int(b)
                key = (device_id, ch)
                prev = last_tele_ch.get(key)
                prev_st = prev[0] if prev else None
                prev_au = prev[1] if prev else None
                if state_i is None and prev_st is not None:
                    state_i = int(prev_st)
                if state_i is None:
                    continue
                fact_au = _effective_auto_for_tele(
                    c, device_id, ch, auto_i, ts_ms, prev_au
                )
                if (
                    prev_st is not None
                    and state_i != prev_st
                    and int(fact_au) == 1
                ):
                    _insert_manual_switch_event(
                        c,
                        device_id=device_id,
                        channel_key=ch,
                        source="tele_auto",
                        ts_ms=ts_ms,
                        prev_auto=-1,
                        new_auto=-1,
                        prev_state=int(prev_st),
                        new_state=int(state_i),
                        meta={"action": "output_change_auto"},
                    )
                cur_chk = c.cursor()
                cur_chk.execute(
                    """SELECT state, auto_mode FROM tele_channel_fact
                    WHERE device_id=? AND channel_key=? ORDER BY ts_ms DESC LIMIT 1""",
                    (device_id, ch),
                )
                db_prev = cur_chk.fetchone()
                db_st = int(db_prev[0]) if db_prev and db_prev[0] is not None else None
                db_au = int(db_prev[1]) if db_prev and db_prev[1] is not None else None
                # 패널 tele auto=0 만으로 DB 홀드 생성 안 함 (UI set_manual 만 홀드)
                if db_st is not None and state_i == db_st and fact_au == db_au:
                    last_tele_ch[key] = (int(state_i), int(fact_au))
                    continue
                if prev is not None and state_i == prev_st and fact_au == prev_au:
                    continue
                c.execute(
                    """INSERT INTO tele_channel_fact
                    (device_id, ts_ms, channel_key, state, auto_mode, on_sec, off_sec)
                    VALUES (?,?,?,?,?,?,?)""",
                    (device_id, ts_ms, ch, state_i, fact_au, on_sec, off_sec),
                )
                last_tele_ch[key] = (int(state_i), int(fact_au))
            for ch, code, rem in guards:
                c.execute(
                    """INSERT INTO pump_guard_event
                    (device_id, ts_ms, channel_key, code, remain_sec, raw_token)
                    VALUES (?,?,?,?,?,?)""",
                    (device_id, ts_ms, ch, code, rem, f"{ch}={code}"),
                )
            return panel_holds

        def _post_cmd(self, c: sqlite3.Connection, body: dict) -> None:
            device_id = str(body.get("device_id") or "cronusfarm-01").strip()
            payload = str(body.get("payload") or "")
            topic = str(body.get("topic") or "")
            ts_ms = int(body.get("ts_ms") or (time.time() * 1000))
            _ensure_device(c, device_id)
            c.execute(
                "INSERT INTO mqtt_cmd_log (device_id, ts_ms, topic, payload) VALUES (?,?,?,?)",
                (device_id, ts_ms, topic, payload),
            )

        def _post_status(self, c: sqlite3.Connection, body: dict) -> None:
            device_id = str(body.get("device_id") or "cronusfarm-01").strip()
            payload = str(body.get("payload") or "")
            topic = str(body.get("topic") or "")
            ts_ms = int(body.get("ts_ms") or (time.time() * 1000))
            _ensure_device(c, device_id)
            c.execute(
                "INSERT INTO mqtt_status_log (device_id, ts_ms, topic, payload) VALUES (?,?,?,?)",
                (device_id, ts_ms, topic, payload),
            )
            pl = payload.strip().lower()
            if pl == "online":
                _arm_boot_schedule_sync(db_path, device_id)
            elif pl == "offline":
                _cancel_boot_schedule_sync(device_id)

        def _post_manual_event(self, c: sqlite3.Connection, body: dict) -> None:
            """UI·시스템 등에서 수동·자동 전환·홀드 분 등 메타를 남김."""
            device_id = str(body.get("device_id") or "cronusfarm-01").strip()
            channel_key = str(
                body.get("channel_key") or body.get("channel") or ""
            ).strip()
            if not channel_key:
                raise ValueError("channel_key required")
            ts_ms = int(body.get("ts_ms") or (time.time() * 1000))
            action = str(body.get("action") or "ui")
            prev_auto = body.get("prev_auto")
            new_auto = body.get("new_auto")
            prev_state = body.get("prev_state")
            new_state = body.get("new_state")
            pa = int(prev_auto) if prev_auto is not None else -1
            na = int(new_auto) if new_auto is not None else -1
            ps = int(prev_state) if prev_state is not None else -1
            ns = int(new_state) if new_state is not None else -1
            if ns < 0 and action == "set_output":
                onv = body.get("on")
                if onv in (True, 1, "1"):
                    ns = 1
                elif onv in (False, 0, "0"):
                    ns = 0
            src = str(body.get("source") or "ui").strip()[:24] or "ui"
            if src not in ("ui", "schedule", "tele_auto", "system", "nr"):
                src = "ui"
            meta: dict[str, object] = {
                "action": action,
                "hold_minutes": body.get("hold_minutes"),
                "mqtt_payload": body.get("mqtt_payload"),
            }
            _insert_manual_switch_event(
                c,
                device_id=device_id,
                channel_key=channel_key,
                source=src,
                ts_ms=ts_ms,
                prev_auto=pa,
                new_auto=na,
                prev_state=ps,
                new_state=ns,
                meta=meta,
            )
            if action not in ("set_output", "set_auto", "set_manual", "revert_auto"):
                return
            cur2 = c.cursor()
            cur2.execute(
                """SELECT state, auto_mode FROM tele_channel_fact
                   WHERE device_id=? AND channel_key=? ORDER BY ts_ms DESC LIMIT 1""",
                (device_id, channel_key),
            )
            row = cur2.fetchone()
            cur_st = int(row[0]) if row and row[0] is not None else None
            cur_au = int(row[1]) if row and row[1] is not None else None
            new_st = cur_st
            new_au = 0 if cur_au is None else int(cur_au)
            if action == "set_output" and ns in (0, 1):
                new_st = ns
                new_au = 0
            elif action == "set_auto":
                new_au = 1
            elif action == "set_manual":
                new_au = 0
            elif action == "revert_auto":
                new_au = 1
            if new_st is None and ps >= 0:
                new_st = ps
            if new_st is not None:
                c.execute(
                    """INSERT INTO tele_channel_fact
                    (device_id, ts_ms, channel_key, state, auto_mode, on_sec, off_sec)
                    VALUES (?,?,?,?,?,?,?)""",
                    (
                        device_id,
                        ts_ms,
                        channel_key,
                        int(new_st),
                        int(new_au),
                        None,
                        None,
                    ),
                )
                last_tele_ch[(device_id, channel_key)] = (int(new_st), int(new_au))

        def _post_sensor(self, c: sqlite3.Connection, body: dict) -> None:
            device_id = str(body.get("device_id") or "cronusfarm-01").strip()
            ts_ms = int(body.get("ts_ms") or (time.time() * 1000))
            zone = str(body.get("zone") or "phw3988").strip()[:64]
            source = str(body.get("source") or "phw3988").strip()[:32]
            raw_json = body.get("raw_json")
            if raw_json is not None and not isinstance(raw_json, str):
                raw_json = json.dumps(raw_json, ensure_ascii=False)
            elif raw_json is not None:
                raw_json = str(raw_json)
            temp_c = body.get("temp_c")
            if temp_c is None and body.get("temp") is not None:
                temp_c = body.get("temp")

            def _f(v: object) -> float | None:
                if v is None or v == "":
                    return None
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return None

            _ensure_device(c, device_id)
            c.execute(
                """INSERT INTO sensor_reading
                (device_id, ts_ms, zone, ph, ec, temp_c, humidity_pct, light_lux, co2_ppm, source, raw_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    device_id,
                    ts_ms,
                    zone,
                    _f(body.get("ph")),
                    _f(body.get("ec")),
                    _f(temp_c),
                    _f(body.get("humidity_pct")),
                    _f(body.get("light_lux")),
                    _f(body.get("co2_ppm")),
                    source,
                    raw_json,
                ),
            )

        def _post_kv(self, c: sqlite3.Connection, body: dict) -> None:
            device_id = str(body.get("device_id") or "cronusfarm-01").strip()
            key = str(body.get("key") or "").strip()
            value = str(body.get("value") if body.get("value") is not None else "")
            if not key:
                raise ValueError("key required")
            _ensure_device(c, device_id)
            c.execute(
                """INSERT INTO settings_kv (device_id, key, value, updated_at)
                VALUES (?,?,?, datetime('now'))
                ON CONFLICT(device_id, key) DO UPDATE SET
                  value=excluded.value, updated_at=datetime('now')""",
                (device_id, key, value),
            )

    return Handler


def main() -> None:
    home = Path.home()
    default_db = home / ".node-red" / "cronusfarm.sqlite"
    db_path = Path(os.environ.get("CRONUSFARM_SQLITE_PATH", str(default_db)))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not db_path.is_file():
        root = Path(__file__).resolve().parents[1]
        sql_file = root / "scripts" / "sql" / "cronusfarm_record_v1.sql"
        if sql_file.is_file():
            conn = sqlite3.connect(str(db_path))
            try:
                conn.executescript(sql_file.read_text(encoding="utf-8"))
                conn.execute(
                    "INSERT OR IGNORE INTO device (device_id, label) VALUES (?, ?)",
                    ("cronusfarm-01", "기본 장치"),
                )
                conn.commit()
            finally:
                conn.close()

    host = os.environ.get("CRONUSFARM_BRIDGE_HOST", "127.0.0.1")
    port = int(os.environ.get("CRONUSFARM_BRIDGE_PORT", "18766"))
    conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=5.0)
    _configure_sqlite_conn(conn)
    _ensure_manual_switch_event_table(conn)
    _ensure_channel_manual_hold_table(conn)
    _ensure_schedule_rule_table(conn)
    try:
        from cronusfarm_admin_api import _ensure_admin_tables

        _ensure_admin_tables(conn)
        conn.commit()
    except Exception as e:
        print(f"[admin] table init skipped: {e}", flush=True)
    seed_flag = os.environ.get("CRONUSFARM_SEED_SCHEDULES", "1").strip().lower()
    if seed_flag not in ("0", "false", "no", "off"):
        try:
            from cronusfarm_schedule_defaults import (
                DEFAULT_DEVICE_ID,
                apply_default_schedules_to_db,
            )

            r = apply_default_schedules_to_db(conn, DEFAULT_DEVICE_ID, force=False)
            if not r.get("skipped"):
                print(
                    f"[seed] default schedules: channels={r.get('channels')} rules={r.get('rules')}",
                    flush=True,
                )
        except Exception as e:
            print(f"[seed] default schedules skipped: {e}", flush=True)
    conn.commit()
    lk = threading.RLock()
    Handler = handle_bridge(conn, db_path, lk)

    class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True

    threading.Thread(
        target=_hold_sweeper_loop, args=(db_path, lk), daemon=True
    ).start()
    _recover_hold_timers(db_path, lk)
    _sweep_revert_manual_without_hold(db_path, lk)

    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"CronusFarm SQLite bridge listening http://{host}:{port} db={db_path}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
