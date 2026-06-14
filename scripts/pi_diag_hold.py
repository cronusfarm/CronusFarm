#!/usr/bin/env python3
import sqlite3
import time

db = "/home/dooly/.node-red/cronusfarm.sqlite"
conn = sqlite3.connect(db)
c = conn.cursor()
now = int(time.time() * 1000)
print("now_ms", now)
c.execute("SELECT name FROM sqlite_master WHERE name='channel_manual_hold'")
print("hold_table", c.fetchone())
try:
    c.execute(
        "SELECT channel_key, expires_ms, hold_minutes FROM channel_manual_hold"
    )
    rows = c.fetchall()
    print("hold_rows", len(rows))
    for r in rows[:20]:
        print("  hold", r, "expired", r[1] <= now)
except Exception as e:
    print("hold err", e)

c.execute(
    """
    SELECT channel_key, state, auto_mode, ts_ms
    FROM tele_channel_fact t
    INNER JOIN (
      SELECT channel_key, MAX(ts_ms) AS mx
      FROM tele_channel_fact WHERE device_id='cronusfarm-01'
      GROUP BY channel_key
    ) u ON t.channel_key = u.channel_key AND t.ts_ms = u.mx
    WHERE t.device_id='cronusfarm-01'
    ORDER BY channel_key
    """
)
manual = 0
for r in c.fetchall():
    if r[2] == 0:
        manual += 1
    print("  tele", r, "age_min", round((now - r[3]) / 60000, 1))
print("manual_count", manual)

c.execute(
    """
    SELECT channel_key, ts_ms, new_auto, source
    FROM manual_switch_event
    WHERE device_id='cronusfarm-01'
    ORDER BY ts_ms DESC LIMIT 10
    """
)
print("audit recent:")
for r in c.fetchall():
    print(" ", r)
conn.close()
