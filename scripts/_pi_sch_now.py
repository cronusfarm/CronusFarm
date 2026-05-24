#!/usr/bin/env python3
"""현재(KST) 스케줄 ON 여부 vs tele S/A."""
import sqlite3
import time
from datetime import datetime
from zoneinfo import ZoneInfo

DB = "/home/dooly/.node-red/cronusfarm.sqlite"
KST = ZoneInfo("Asia/Seoul")
dev = "cronusfarm-01"

# minimal: read tele S from latest sample
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute(
    "SELECT raw FROM tele_sample WHERE device_id=? ORDER BY ts_ms DESC LIMIT 1",
    (dev,),
)
raw = (cur.fetchone() or [""])[0] or ""
s_part = a_part = ""
for seg in raw.split("|"):
    seg = seg.strip()
    if seg.startswith("S:"):
        s_part = seg[2:].strip()
    elif seg.startswith("A:"):
        a_part = seg[2:].strip()

def parse_kv(s):
    out = {}
    for tok in s.split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            out[k] = v
    return out

kv_s = parse_kv(s_part)
kv_a = parse_kv(a_part)
now = datetime.now(KST)
dow = now.weekday()  # Mon=0
mins = now.hour * 60 + now.minute
print("now", now.strftime("%Y-%m-%d %H:%M KST"), "dow", dow, "min", mins)
print("\n--- tele S (릴레이 실제) ---")
for k in sorted(kv_s.keys()):
    print(f"  {k}: {'ON' if kv_s[k]=='1' else 'OFF'}")
print("\n--- tele A (자동=1/수동=0) — ON 아님! ---")
for k in sorted(kv_a.keys()):
    if kv_a[k] == "1":
        print(f"  {k}: AUTO")

cur.execute(
    """SELECT channel_key, rule_kind, on_min, off_min, enabled, slot_index
    FROM schedule_rule WHERE device_id=? AND enabled=1 ORDER BY channel_key, slot_index""",
    (dev,),
)
print("\n--- enabled schedule (on~off min) ---")
for r in cur.fetchall():
    ch, kind, on_m, off_m, en, sl = r
    on_h, on_mi = divmod(int(on_m), 60)
    off_h, off_mi = divmod(int(off_m), 60)
    in_win = on_m <= mins < off_m if int(on_m) < int(off_m) else (mins >= on_m or mins < off_m)
    print(
        f"  {ch} [{kind}] {on_h:02d}:{on_mi:02d}-{off_h:02d}:{off_mi:02d} "
        f"{'*NOW*' if in_win else ''}"
    )
