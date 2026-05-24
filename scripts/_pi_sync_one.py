#!/usr/bin/env python3
import sqlite3
import subprocess
import sys

sys.path.insert(0, "/home/dooly/CronusFarm/scripts")
from cronusfarm_sqlite_bridge import _mqtt_publish_all_auto, _sync_device_schedules_mqtt_full
import threading

db = "/home/dooly/.node-red/cronusfarm.sqlite"
dev = "cronusfarm-01"
lock = threading.Lock()
conn = sqlite3.connect(db)
conn.execute("PRAGMA foreign_keys = ON")
n, auto_n = _sync_device_schedules_mqtt_full(conn, db, lock, dev)
print({"channels_published": n, "auto_published": auto_n})
subprocess.run(
    ["mosquitto_pub", "-h", "127.0.0.1", "-t", f"cronusfarm/{dev}/cmd", "-m", "rtc_local=20260523164500"],
    check=False,
)
