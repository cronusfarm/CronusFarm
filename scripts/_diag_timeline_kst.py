#!/usr/bin/env python3
"""tele_channel_fact 타임라인 샘플 — KST 시각으로 출력."""
import sqlite3
import time
from datetime import datetime
from zoneinfo import ZoneInfo

DB = "/home/dooly/.node-red/cronusfarm.sqlite"
KST = ZoneInfo("Asia/Seoul")
now_ms = int(time.time() * 1000)
cutoff = now_ms - 24 * 3600 * 1000


def fmt(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=KST).strftime("%Y-%m-%d %H:%M:%S KST")


conn = sqlite3.connect(DB)
cur = conn.cursor()
print("now", fmt(now_ms), "cutoff", fmt(cutoff))
for ch in ("led_a1", "pump_d1"):
    cur.execute(
        """SELECT ts_ms, state, auto_mode FROM tele_channel_fact
           WHERE device_id='cronusfarm-01' AND channel_key=? AND ts_ms >= ?
           ORDER BY ts_ms DESC LIMIT 8""",
        (ch, cutoff),
    )
    rows = list(cur.fetchall())
    print(f"\n=== {ch} (last 8 in 24h window) ===")
    for r in reversed(rows):
        ts, st, au = int(r[0]), r[1], r[2]
        flag = " FUTURE" if ts > now_ms + 300000 else ""
        print(f"  {fmt(ts)} state={st} auto={au}{flag}")
    cur.execute(
        """SELECT count(*) FROM tele_channel_fact
           WHERE device_id='cronusfarm-01' AND channel_key=? AND ts_ms > ?""",
        (ch, now_ms),
    )
    print("  future count:", cur.fetchone()[0])
conn.close()
