#!/usr/bin/env python3
import sqlite3
r = sqlite3.connect("/home/dooly/.node-red/cronusfarm.sqlite").execute(
    "SELECT substr(raw,1,800) FROM tele_sample WHERE device_id='cronusfarm-01' ORDER BY ts_ms DESC LIMIT 1"
).fetchone()
print(r[0] if r else "none")
