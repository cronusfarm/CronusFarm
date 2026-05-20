#!/usr/bin/env python3
"""CronusFarm 기본 스케줄을 SQLite에 기록하고(선택) MQTT 동기화."""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from cronusfarm_schedule_defaults import (  # noqa: E402
    DEFAULT_DEVICE_ID,
    apply_default_schedules_to_db,
)


def main() -> None:
    ap = argparse.ArgumentParser(description="CronusFarm 기본 스케줄 DB 시드")
    ap.add_argument("--device-id", default=DEFAULT_DEVICE_ID)
    ap.add_argument(
        "--db",
        default=os.environ.get(
            "CRONUSFARM_SQLITE_PATH",
            str(Path.home() / ".node-red" / "cronusfarm.sqlite"),
        ),
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="기존 schedule_rule 을 삭제하고 기본값으로 덮어씀",
    )
    ap.add_argument(
        "--sync-mqtt",
        action="store_true",
        help="브리지 POST /api/schedule/seed_defaults (MQTT 포함)",
    )
    ap.add_argument(
        "--bridge",
        default=os.environ.get(
            "CRONUSFARM_BRIDGE_URL", "http://127.0.0.1:18766"
        ),
    )
    args = ap.parse_args()

    if args.sync_mqtt:
        url = f"{args.bridge.rstrip('/')}/api/schedule/seed_defaults"
        payload = {"device_id": args.device_id, "force": bool(args.force)}
        req = urllib.request.Request(
            url,
            data=__import__("json").dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                print(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            print(e.read().decode("utf-8", errors="replace"), file=sys.stderr)
            raise SystemExit(1) from e
        return

    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"DB 없음: {db_path}", file=sys.stderr)
        raise SystemExit(1)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        result = apply_default_schedules_to_db(
            conn, args.device_id, force=bool(args.force)
        )
        print(result)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
