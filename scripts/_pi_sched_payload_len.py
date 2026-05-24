#!/usr/bin/env python3
import json
import sqlite3
import urllib.parse

DB = "/home/dooly/.node-red/cronusfarm.sqlite"
DEV = "cronusfarm-01"

conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute(
    "SELECT DISTINCT channel_key FROM schedule_rule WHERE device_id=?",
    (DEV,),
)
for (ch,) in cur.fetchall():
    cur.execute(
        """SELECT rule_kind, dow_mask, slot_index, on_min, off_min, on_sec, off_sec, enabled
           FROM schedule_rule WHERE device_id=? AND channel_key=? ORDER BY slot_index""",
        (DEV, ch),
    )
    rules = []
    for r in cur.fetchall():
        rk, dm, sl, on_m, off_m, on_s, off_s, en = r
        rules.append(
            {
                "rule_kind": rk,
                "dow_mask": dm,
                "slot_index": sl,
                "on_min": on_m,
                "off_min": off_m,
                "on_sec": on_s,
                "off_sec": off_s,
                "enabled": en,
            }
        )
    env = {"sch_ver": 1, "channel": ch, "rules": rules}
    raw = json.dumps(env, ensure_ascii=False, separators=(",", ":"))
    pay = "SCHED_JSON=" + urllib.parse.quote(raw, safe="")
    print(f"{ch}: raw={len(raw)} encoded={len(pay)}")
