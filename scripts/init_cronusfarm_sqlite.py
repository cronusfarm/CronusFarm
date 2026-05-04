#!/usr/bin/env python3
"""CronusFarm SQLite DB 초기화 — 스키마 적용 및 기본 장치 행 삽입."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    sql_path = root / "scripts" / "sql" / "cronusfarm_record_v1.sql"
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "db",
        nargs="?",
        default=str(root / "data" / "cronusfarm.sqlite"),
        help="SQLite 파일 경로",
    )
    args = ap.parse_args()
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(sql_path.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT OR IGNORE INTO device (device_id, label) VALUES (?, ?)",
            ("cronusfarm-01", "기본 장치"),
        )
        conn.commit()
        print(f"OK SQLite 초기화: {db_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
