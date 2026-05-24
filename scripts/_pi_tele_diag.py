#!/usr/bin/env python3
import sqlite3
import time
from datetime import datetime
from zoneinfo import ZoneInfo

DB = "/home/dooly/.node-red/cronusfarm.sqlite"
KST = ZoneInfo("Asia/Seoul")
dev = "cronusfarm-01"

conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute(
    "SELECT ts_ms, raw FROM tele_sample WHERE device_id=? ORDER BY ts_ms DESC LIMIT 3",
    (dev,),
)
now = int(time.time() * 1000)
print("now", datetime.fromtimestamp(now / 1000, tz=KST).strftime("%F %T KST"))
for ts, raw in cur.fetchall():
    age = (now - int(ts)) / 1000
    print(f"\n--- tele_sample age={age:.0f}s ts={ts}")
    print((raw or "")[:500])

print("\n--- tele_channel_fact latest per channel")
cur.execute(
    """
    SELECT channel_key, state, auto_mode, ts_ms
    FROM tele_channel_fact t
    INNER JOIN (
      SELECT channel_key, MAX(ts_ms) AS mx FROM tele_channel_fact WHERE device_id=? GROUP BY channel_key
    ) u ON t.channel_key=u.channel_key AND t.ts_ms=u.mx
    WHERE t.device_id=?
    ORDER BY channel_key
    """,
    (dev, dev),
)
for r in cur.fetchall():
    print(f"  {r[0]}: state={r[1]} auto={r[2]}")
