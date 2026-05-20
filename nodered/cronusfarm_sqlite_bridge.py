#!/usr/bin/env python3
"""
CronusFarm SQLite HTTP 브리지 (표준 라이브러리만 사용).
Pi에서 Node-RED가 tele/cmd를 POST하면 SQLite에 적재합니다.

환경변수:
  CRONUSFARM_SQLITE_PATH  DB 파일 경로 (기본: ~/.node-red/cronusfarm.sqlite)
  CRONUSFARM_BRIDGE_HOST  바인드 주소 (기본: 127.0.0.1)
  CRONUSFARM_BRIDGE_PORT  포트 (기본: 18766)
  CRONUSFARM_SCHEDULE_MQTT  0/false/off 시에만 SCHED_JSON MQTT 발행 생략(그 외는 기본 발행, mosquitto_pub 필요)
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
GET  /api/channel/timeline?device_id=...&channel=...&hours=24  JSON: tele_channel_fact 시계열(그래프). anchor_ts_ms=창 시작(ms), points는 창 시작·끝 보간 포함
POST /api/channel/backfill  JSON: { device_id, channel|channel_key, hours? } tele_sample→tele_channel_fact 누락 행 보강
GET  /api/channel/status?device_id=...  JSON: 채널별 최신 state·auto_mode(마지막 tele 적재)
GET  /api/audit_log?device_id=...&limit=100&channel=&since_ms=0  JSON: manual_switch_event 감사 로그(수동·스케줄 저장·자동 ON/OFF)
POST /ingest/manual_event  JSON: UI 수동 조작 로그 → manual_switch_event (source: ui|system|…)
POST /ingest/sensor  JSON: PHW3988 등 → sensor_reading (ph, ec, temp_c, zone, raw_json)
GET  /api/sensor/latest?device_id=...&zone=phw3988  JSON: 최신 sensor_reading 1건
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
) -> tuple[str, int]:
    """PUT /api/schedule 직후 Arduino cmd 토픽으로 SCHED_JSON 발행(기본 on). 반환: (상태, sch_ver)."""
    sch_ver = int(time.time())
    flag = os.environ.get("CRONUSFARM_SCHEDULE_MQTT", "").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return ("skipped_env", sch_ver)
    exe = shutil.which("mosquitto_pub")
    if not exe:
        return ("no_mosquitto_pub", sch_ver)
    host = os.environ.get("CRONUSFARM_MQTT_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = os.environ.get("CRONUSFARM_MQTT_PORT", "1883").strip() or "1883"
    topic = f"cronusfarm/{device_id}/cmd"
    envelope = {
        "sch_ver": sch_ver,
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
        return ("publish_error", sch_ver)
    return ("published", sch_ver)


ALL_CHANNELS = [
    "led_a1",
    "led_a2",
    "led_b1",
    "led_b2",
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
                if hours < 1 or hours > 168:
                    hours = 24
                now_ms = int(time.time() * 1000)
                cutoff = now_ms - hours * 3600 * 1000
                anchor_ts_ms = cutoff
                with lock:
                    cur = conn.cursor()
                    cur.execute(
                        """SELECT ts_ms, state, auto_mode
                        FROM tele_channel_fact
                        WHERE device_id=? AND channel_key=? AND ts_ms >= ?
                        ORDER BY ts_ms ASC
                        LIMIT 4000""",
                        (device_id, channel, cutoff),
                    )
                    points: list[dict[str, object]] = [
                        {
                            "ts_ms": int(r[0]),
                            "state": r[1],
                            "auto_mode": r[2],
                        }
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
                            {
                                "ts_ms": anchor_ts_ms,
                                "state": pre[1],
                                "auto_mode": pre[2],
                            },
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
                    if points:
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
                body = {
                    "device_id": device_id,
                    "channel_key": channel,
                    "hours": hours,
                    "anchor_ts_ms": anchor_ts_ms,
                    "window_end_ms": now_ms,
                    "points": points,
                }
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
                with lock:
                    cur = conn.cursor()
                    cur.execute(
                        """
                        SELECT t.channel_key, t.state, t.auto_mode, t.ts_ms
                        FROM tele_channel_fact t
                        INNER JOIN (
                          SELECT channel_key, MAX(ts_ms) AS mx
                          FROM tele_channel_fact
                          WHERE device_id=?
                          GROUP BY channel_key
                        ) u ON t.channel_key = u.channel_key AND t.ts_ms = u.mx
                        WHERE t.device_id=?
                        """,
                        (device_id, device_id),
                    )
                    chans = {}
                    for r in cur.fetchall():
                        chans[str(r[0])] = {
                            "state": r[1],
                            "auto_mode": r[2],
                            "ts_ms": int(r[3]) if r[3] is not None else None,
                        }
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
                with lock:
                    if path == "/ingest/tele":
                        self._post_tele(conn, body)
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
                key = (device_id, ch)
                prev = last_tele_ch.get(key)
                prev_st = prev[0] if prev else None
                prev_au = prev[1] if prev else None
                eff_au = auto_i if auto_i is not None else prev_au
                if eff_au is None:
                    eff_au = 0
                if (
                    state_i is not None
                    and prev_st is not None
                    and state_i != prev_st
                    and int(eff_au) == 1
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
                c.execute(
                    """INSERT INTO tele_channel_fact
                    (device_id, ts_ms, channel_key, state, auto_mode, on_sec, off_sec)
                    VALUES (?,?,?,?,?,?,?)""",
                    (device_id, ts_ms, ch, state_i, auto_i, on_sec, off_sec),
                )
                n_st = state_i if state_i is not None else prev_st
                n_au = auto_i if auto_i is not None else prev_au
                if n_au is None:
                    n_au = 0
                if n_st is not None:
                    last_tele_ch[key] = (int(n_st), int(n_au))
                elif prev is not None:
                    pst = prev_st if prev_st is not None else 0
                    last_tele_ch[key] = (int(pst), int(n_au))
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
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    _ensure_manual_switch_event_table(conn)
    _ensure_schedule_rule_table(conn)
    conn.commit()
    lk = threading.Lock()
    Handler = handle_bridge(conn, db_path, lk)

    class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True

    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"CronusFarm SQLite bridge listening http://{host}:{port} db={db_path}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
