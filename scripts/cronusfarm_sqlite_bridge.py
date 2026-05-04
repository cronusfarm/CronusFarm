#!/usr/bin/env python3
"""
CronusFarm SQLite HTTP 브리지 (표준 라이브러리만 사용).
Pi에서 Node-RED가 tele/cmd를 POST하면 SQLite에 적재합니다.

환경변수:
  CRONUSFARM_SQLITE_PATH  DB 파일 경로 (기본: ~/.node-red/cronusfarm.sqlite)
  CRONUSFARM_BRIDGE_HOST  바인드 주소 (기본: 127.0.0.1)
  CRONUSFARM_BRIDGE_PORT  포트 (기본: 18766)
  CRONUSFARM_SCHEDULE_MQTT  1/true 시 PUT /api/schedule 성공 후 mosquitto_pub으로 cmd 발행(선택)
  CRONUSFARM_MQTT_HOST      mosquitto_pub -h (기본: 127.0.0.1)
  CRONUSFARM_MQTT_PORT      mosquitto_pub -p (기본: 1883)

POST /ingest/tele  JSON: { device_id, topic?, raw, ts_ms? }
POST /ingest/cmd   JSON: { device_id, topic?, payload, ts_ms? }
POST /ingest/status JSON: { device_id, topic?, payload, ts_ms? }
POST /settings/kv JSON: { device_id, key, value }
GET  /health
GET  /api/snapshot?device_id=...  JSON: tele/cmd 건수·마지막 tele 시각·settings_kv 목록
GET  /api/schedule?device_id=...&channel=...  JSON: schedule_rule 목록
PUT  /api/schedule?device_id=...&channel=...  JSON: rules[] 에 rule_kind(window|cycle), window 시 on_min/off_min(분), cycle 시 on_sec/off_sec(초)
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
from urllib.parse import parse_qs, quote, urlparse

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


def _publish_schedule_mqtt(
    *,
    device_id: str,
    channel_key: str,
    rules: list[dict[str, object]],
) -> None:
    """Pi에 mosquitto_pub 있을 때만 동작. 펌웨어는 SCHED_JSON 파싱을 추후 구현."""
    flag = os.environ.get("CRONUSFARM_SCHEDULE_MQTT", "").strip().lower()
    if flag not in ("1", "true", "yes", "on"):
        return
    exe = shutil.which("mosquitto_pub")
    if not exe:
        return
    host = os.environ.get("CRONUSFARM_MQTT_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = os.environ.get("CRONUSFARM_MQTT_PORT", "1883").strip() or "1883"
    topic = f"cronusfarm/{device_id}/cmd"
    envelope = {
        "sch_ver": int(time.time()),
        "channel": channel_key,
        "rules": rules,
    }
    raw_j = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
    payload = "SCHED_JSON=" + quote(raw_j, safe="")
    try:
        subprocess.run(
            [exe, "-h", host, "-p", port, "-t", topic, "-m", payload],
            check=False,
            timeout=8,
            capture_output=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


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
]


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


def handle_bridge(conn: sqlite3.Connection, db_path: Path, lock: threading.Lock) -> type[BaseHTTPRequestHandler]:
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
                "Access-Control-Allow-Methods", "GET, PUT, POST, OPTIONS"
            )
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

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
            if path == "/health":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")
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
                    rules = []
                    for r in cur.fetchall():
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
                        rules.append(entry)
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

        def do_PUT(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/api/schedule":
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
                            on_sec = int(row.get("on_sec", 0))
                            off_sec = int(row.get("off_sec", 0))
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
                                "on_min": 0,
                                "off_min": 0,
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
                                    0,
                                    0,
                                    1 if en else 0,
                                    "cycle",
                                    on_sec,
                                    off_sec,
                                ),
                            )
                        else:
                            on_m = int(row.get("on_min", 0))
                            off_m = int(row.get("off_min", 0))
                            if on_m < 0 or on_m > 1439 or off_m < 0 or off_m > 1439:
                                raise ValueError("on_min/off_min 0..1439")
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
                _publish_schedule_mqtt(
                    device_id=device_id,
                    channel_key=channel,
                    rules=mqtt_rules,
                )
                out = {"ok": True, "saved": len(mqtt_rules)}
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
            try:
                with lock:
                    if path == "/ingest/tele":
                        self._post_tele(conn, body)
                    elif path == "/ingest/cmd":
                        self._post_cmd(conn, body)
                    elif path == "/ingest/status":
                        self._post_status(conn, body)
                    elif path == "/settings/kv":
                        self._post_kv(conn, body)
                    else:
                        self.send_error(404)
                        return
                    conn.commit()
                self.send_response(204)
                self.end_headers()
            except Exception as e:
                with lock:
                    conn.rollback()
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode("utf-8"))

        def _post_tele(self, c: sqlite3.Connection, body: dict) -> None:
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
                c.execute(
                    """INSERT INTO tele_channel_fact
                    (device_id, ts_ms, channel_key, state, auto_mode, on_sec, off_sec)
                    VALUES (?,?,?,?,?,?,?)""",
                    (device_id, ts_ms, ch, state_i, auto_i, on_sec, off_sec),
                )
            for ch, code, rem in guards:
                c.execute(
                    """INSERT INTO pump_guard_event
                    (device_id, ts_ms, channel_key, code, remain_sec, raw_token)
                    VALUES (?,?,?,?,?,?)""",
                    (device_id, ts_ms, ch, code, rem, f"{ch}={code}"),
                )

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
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    lk = threading.Lock()
    Handler = handle_bridge(conn, db_path, lk)

    class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True

    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"CronusFarm SQLite bridge listening http://{host}:{port} db={db_path}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
