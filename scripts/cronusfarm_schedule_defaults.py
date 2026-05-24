"""CronusFarm 기본 스케줄 규칙 (SQLite·브리지 시드·문서 공통)."""

from __future__ import annotations

import sqlite3
from typing import Any

DEFAULT_DEVICE_ID = "cronusfarm-01"

# rule_kind: window | cycle
# cycle 규칙의 on_min/off_min: 해당 시간대에만 주기 적용 (0,0 이면 하루 종일)
DEFAULT_SCHEDULE_RULES: dict[str, list[dict[str, Any]]] = {
    "led_a2": [
        {
            "rule_kind": "window",
            "dow_mask": 127,
            "slot_index": 0,
            "on_min": 390,
            "off_min": 1110,
            "enabled": 1,
        },
    ],
    "led_a1": [
        {
            "rule_kind": "window",
            "dow_mask": 127,
            "slot_index": 0,
            "on_min": 390,
            "off_min": 1110,
            "enabled": 1,
        },
    ],
    "led_b1": [
        {
            "rule_kind": "window",
            "dow_mask": 127,
            "slot_index": 0,
            "on_min": 450,
            "off_min": 1050,
            "enabled": 1,
        },
    ],
    "led_b2": [
        {
            "rule_kind": "window",
            "dow_mask": 127,
            "slot_index": 0,
            "on_min": 450,
            "off_min": 1050,
            "enabled": 1,
        },
    ],
    "pump_a1": [
        {
            "rule_kind": "cycle",
            "dow_mask": 127,
            "slot_index": 0,
            "on_min": 0,
            "off_min": 0,
            "on_sec": 900,
            "off_sec": 1200,
            "enabled": 1,
        },
    ],
    "pump_a2": [
        {
            "rule_kind": "cycle",
            "dow_mask": 127,
            "slot_index": 0,
            "on_min": 540,
            "off_min": 1020,
            "on_sec": 600,
            "off_sec": 3000,
            "enabled": 1,
        },
        {
            "rule_kind": "cycle",
            "dow_mask": 127,
            "slot_index": 1,
            "on_min": 0,
            "off_min": 540,
            "on_sec": 300,
            "off_sec": 3300,
            "enabled": 1,
        },
        {
            "rule_kind": "cycle",
            "dow_mask": 127,
            "slot_index": 2,
            "on_min": 1020,
            "off_min": 1440,
            "on_sec": 300,
            "off_sec": 3300,
            "enabled": 1,
        },
    ],
    "pump_b2": [
        {
            "rule_kind": "cycle",
            "dow_mask": 127,
            "slot_index": 0,
            "on_min": 540,
            "off_min": 1020,
            "on_sec": 600,
            "off_sec": 3000,
            "enabled": 1,
        },
        {
            "rule_kind": "cycle",
            "dow_mask": 127,
            "slot_index": 1,
            "on_min": 0,
            "off_min": 540,
            "on_sec": 300,
            "off_sec": 3300,
            "enabled": 1,
        },
        {
            "rule_kind": "cycle",
            "dow_mask": 127,
            "slot_index": 2,
            "on_min": 1020,
            "off_min": 1440,
            "on_sec": 300,
            "off_sec": 3300,
            "enabled": 1,
        },
    ],
    "pump_b1": [
        {
            "rule_kind": "cycle",
            "dow_mask": 127,
            "slot_index": 0,
            "on_min": 450,
            "off_min": 1050,
            "on_sec": 180,
            "off_sec": 420,
            "enabled": 1,
        },
        {
            "rule_kind": "cycle",
            "dow_mask": 127,
            "slot_index": 1,
            "on_min": 0,
            "off_min": 450,
            "on_sec": 60,
            "off_sec": 540,
            "enabled": 1,
        },
        {
            "rule_kind": "cycle",
            "dow_mask": 127,
            "slot_index": 2,
            "on_min": 1050,
            "off_min": 1440,
            "on_sec": 60,
            "off_sec": 540,
            "enabled": 1,
        },
    ],
    "pump_c1": [
        {
            "rule_kind": "cycle",
            "dow_mask": 127,
            "slot_index": 0,
            "on_min": 0,
            "off_min": 0,
            "on_sec": 60,
            "off_sec": 3540,
            "enabled": 1,
        },
    ],
    "pump_c2": [
        {
            "rule_kind": "cycle",
            "dow_mask": 127,
            "slot_index": 0,
            "on_min": 0,
            "off_min": 0,
            "on_sec": 60,
            "off_sec": 7140,
            "enabled": 1,
        },
    ],
    "pump_d1": [
        {
            "rule_kind": "cycle",
            "dow_mask": 127,
            "slot_index": 0,
            "on_min": 0,
            "off_min": 0,
            "on_sec": 60,
            "off_sec": 10740,
            "enabled": 1,
        },
    ],
    "pump_d2": [
        {
            "rule_kind": "cycle",
            "dow_mask": 127,
            "slot_index": 0,
            "on_min": 0,
            "off_min": 0,
            "on_sec": 60,
            "off_sec": 14340,
            "enabled": 1,
        },
    ],
    "fan_a1": [
        {
            "rule_kind": "window",
            "dow_mask": 127,
            "slot_index": 0,
            "on_min": 360,
            "off_min": 1440,
            "enabled": 1,
        },
    ],
    "fan_a2": [
        {
            "rule_kind": "window",
            "dow_mask": 127,
            "slot_index": 0,
            "on_min": 360,
            "off_min": 1440,
            "enabled": 1,
        },
    ],
    "fan_b1": [
        {
            "rule_kind": "window",
            "dow_mask": 127,
            "slot_index": 0,
            "on_min": 360,
            "off_min": 1440,
            "enabled": 1,
        },
    ],
    "fan_b2": [
        {
            "rule_kind": "window",
            "dow_mask": 127,
            "slot_index": 0,
            "on_min": 360,
            "off_min": 1440,
            "enabled": 1,
        },
    ],
}


def _insert_rules(
    cur: sqlite3.Cursor, device_id: str, channel_key: str, rules: list[dict[str, Any]]
) -> int:
    n = 0
    for i, row in enumerate(rules):
        rk = str(row.get("rule_kind") or "window").strip().lower()
        dow = int(row.get("dow_mask", 127))
        slot = int(row.get("slot_index", i))
        en = int(row.get("enabled", 1))
        if rk == "cycle":
            on_m = int(row.get("on_min", 0))
            off_m = int(row.get("off_min", 0))
            on_sec = int(row.get("on_sec", 0))
            off_sec = int(row.get("off_sec", 0))
            cur.execute(
                """INSERT INTO schedule_rule
                   (device_id, channel_key, dow_mask, slot_index, on_min, off_min,
                    enabled, rule_kind, on_sec, off_sec, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?, datetime('now'))""",
                (
                    device_id,
                    channel_key,
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
            cur.execute(
                """INSERT INTO schedule_rule
                   (device_id, channel_key, dow_mask, slot_index, on_min, off_min,
                    enabled, rule_kind, on_sec, off_sec, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?, datetime('now'))""",
                (
                    device_id,
                    channel_key,
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
        n += 1
    return n


def apply_default_schedules_to_db(
    conn: sqlite3.Connection,
    device_id: str = DEFAULT_DEVICE_ID,
    *,
    force: bool = False,
) -> dict[str, int]:
    """기본 스케줄을 DB에 기록. force=False 이면 해당 장치에 규칙이 없을 때만."""
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM schedule_rule WHERE device_id=?",
        (device_id,),
    )
    existing = int(cur.fetchone()[0])
    if existing > 0 and not force:
        return {"skipped": 1, "channels": 0, "rules": 0}

    if force:
        cur.execute("DELETE FROM schedule_rule WHERE device_id=?", (device_id,))

    cur.execute(
        "INSERT OR IGNORE INTO device (device_id, label) VALUES (?, ?)",
        (device_id, "기본 장치"),
    )

    total_rules = 0
    channels = 0
    for channel_key, rules in DEFAULT_SCHEDULE_RULES.items():
        if force:
            cur.execute(
                "DELETE FROM schedule_rule WHERE device_id=? AND channel_key=?",
                (device_id, channel_key),
            )
        total_rules += _insert_rules(cur, device_id, channel_key, rules)
        channels += 1
    conn.commit()
    return {"skipped": 0, "channels": channels, "rules": total_rules}
