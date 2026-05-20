#!/usr/bin/env python3
"""Pi에서 모든 채널 수동→자동 일괄 복귀 (브리지 모듈 재사용)."""
from __future__ import annotations

import sqlite3
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import cronusfarm_sqlite_bridge as bridge  # noqa: E402

DEVICE = "cronusfarm-01"
DB = Path(
    __import__("os").environ.get(
        "CRONUSFARM_SQLITE_PATH", str(Path.home() / ".node-red" / "cronusfarm.sqlite")
    )
)


def main() -> None:
    db_path = DB
    lock = threading.Lock()
    conn = sqlite3.connect(str(db_path))
    try:
        bridge._ensure_channel_manual_hold_table(conn)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT t.channel_key
            FROM tele_channel_fact t
            INNER JOIN (
              SELECT channel_key, MAX(ts_ms) AS mx
              FROM tele_channel_fact WHERE device_id=?
              GROUP BY channel_key
            ) u ON t.channel_key = u.channel_key AND t.ts_ms = u.mx
            WHERE t.device_id=? AND t.auto_mode = 0
            """,
            (DEVICE, DEVICE),
        )
        channels = [str(r[0]) for r in cur.fetchall()]
    finally:
        conn.close()

    print(f"manual channels: {len(channels)}", flush=True)
    for ch in channels:
        bridge._revert_channel_to_auto(db_path, lock, DEVICE, ch)
        print(f"  reverted {ch}", flush=True)
        time.sleep(0.05)

    conn2 = sqlite3.connect(str(db_path))
    cur2 = conn2.cursor()
    cur2.execute(
        """
        SELECT channel_key, auto_mode FROM tele_channel_fact t
        INNER JOIN (
          SELECT channel_key, MAX(ts_ms) mx FROM tele_channel_fact
          WHERE device_id=? GROUP BY channel_key
        ) u ON t.channel_key=u.channel_key AND t.ts_ms=u.mx
        WHERE t.device_id=? AND t.auto_mode=0
        """,
        (DEVICE, DEVICE),
    )
    left = cur2.fetchall()
    conn2.close()
    print(f"still manual: {len(left)}", left[:5], flush=True)


if __name__ == "__main__":
    main()
