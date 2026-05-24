#!/usr/bin/env python3
import sqlite3
from datetime import datetime

db = "/home/dooly/.node-red/cronusfarm.sqlite"
dev = "cronusfarm-01"
c = sqlite3.connect(db)
c.row_factory = sqlite3.Row
now = datetime.now()
mins = now.hour * 60 + now.minute
print(f"local_now={now.strftime('%Y-%m-%d %H:%M')} mins={mins}")
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY 1")]
print("tables:", ", ".join(tables))
if "channel" in tables:
    print("=== channel ===")
    for r in c.execute(
        "SELECT channel_key, mode, enabled, manual_state FROM channel WHERE device_id=? ORDER BY channel_key",
        (dev,),
    ):
        print(f"{r['channel_key']:12} mode={r['mode']:6} en={r['enabled']} manual={r['manual_state']}")
if "tele_channel_fact" in tables:
    print("=== tele_channel_fact (latest auto_mode / state) ===")
    for r in c.execute(
        """
        SELECT t.channel_key, t.state, t.auto_mode, t.ts_ms
        FROM tele_channel_fact t
        INNER JOIN (
          SELECT device_id, channel_key, MAX(ts_ms) AS mx
          FROM tele_channel_fact WHERE device_id=?
          GROUP BY device_id, channel_key
        ) u ON t.device_id=u.device_id AND t.channel_key=u.channel_key AND t.ts_ms=u.mx
        WHERE t.device_id=? ORDER BY t.channel_key
        """,
        (dev, dev),
    ):
        print(f"{r['channel_key']:12} state={r['state']} auto={r['auto_mode']} ts={r['ts_ms']}")
print("=== rules (active window check) ===")
for ch in ("led_a1", "pump_a1", "pump_b1", "fan_a1"):
    print(f"-- {ch} --")
    for r in c.execute(
        """SELECT rule_kind, on_min, off_min, on_sec, off_sec, enabled, dow_mask
           FROM schedule_rule WHERE device_id=? AND channel_key=? ORDER BY on_min""",
        (dev, ch),
    ):
        st, en = r["on_min"], r["off_min"]
        in_win = False
        if r["rule_kind"] == "window" and en > st:
            in_win = st <= mins < en
        print(
            f"  {r['rule_kind']:8} on_min={st} off_min={en} on_sec={r['on_sec']} off_sec={r['off_sec']} en={r['enabled']} in_win={in_win}"
        )
