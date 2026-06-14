#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pi: tele_channel_fact·tele_sample 타임라인 진단."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

DB_CAND = [
    Path("/home/dooly/.node-red/cronusfarm.sqlite"),
    Path("/home/dooly/CronusFarm/db/smartfarm.sqlite"),
    Path("/home/pi/.node-red/cronusfarm.sqlite"),
]
CHS = [
    "led_a1", "led_a2", "fan_a1", "fan_a2", "led_b1", "led_b2", "fan_b1", "fan_b2",
    "pump_c1", "pump_c2", "pump_d1", "pump_d2",
]
DEV = "cronusfarm-01"


def find_db() -> Path:
    for p in DB_CAND:
        if p.is_file():
            return p
    raise SystemExit("DB not found")


def fmt_ms(ms: int | None) -> str:
    if ms is None:
        return "-"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ms / 1000))


def main() -> None:
    db = find_db()
    print("DB", db)
    conn = sqlite3.connect(str(db))
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*), MIN(ts_ms), MAX(ts_ms) FROM tele_sample WHERE device_id=?",
        (DEV,),
    )
    n, t0, t1 = cur.fetchone()
    print(f"tele_sample n={n} {fmt_ms(t0)} .. {fmt_ms(t1)}")
    print("--- tele_channel_fact (today window) ---")
    now = int(time.time() * 1000)
    from datetime import datetime
    from zoneinfo import ZoneInfo

    kst = ZoneInfo("Asia/Seoul")
    dt = datetime.fromtimestamp(now / 1000, tz=kst)
    anchor = int(
        dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000
    )
    for ch in CHS:
        cur.execute(
            """SELECT COUNT(*), MIN(ts_ms), MAX(ts_ms),
                      (SELECT state FROM tele_channel_fact
                       WHERE device_id=? AND channel_key=? AND ts_ms < ?
                       ORDER BY ts_ms DESC LIMIT 1)
               FROM tele_channel_fact
               WHERE device_id=? AND channel_key=? AND ts_ms >= ?""",
            (DEV, ch, anchor, DEV, ch, anchor),
        )
        cnt, mn, mx, pre = cur.fetchone()
        cur.execute(
            """SELECT state FROM tele_channel_fact
               WHERE device_id=? AND channel_key=? ORDER BY ts_ms DESC LIMIT 1""",
            (DEV, ch),
        )
        last = cur.fetchone()
        print(
            f"{ch:10} cnt={cnt:5} range={fmt_ms(mn)}..{fmt_ms(mx)} pre<{anchor}={pre} last={last}"
        )
    conn.close()


if __name__ == "__main__":
    main()
