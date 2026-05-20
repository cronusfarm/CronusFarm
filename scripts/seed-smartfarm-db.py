#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
스마트팜(SQLite) DB 생성/스키마 적용/테스트 데이터 시딩 스크립트.

- 목적: 4/1 ~ 오늘까지의 "개연성 있는" 환경/장치/알람/스케줄 데이터를 채워
  Grafana/개발에서 화면을 빠르게 검증할 수 있게 한다.
- 주의: 운영 환경에서는 시드 데이터가 아니라 실측/실행 로그를 적재해야 한다.
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
import os
import random
import sqlite3
from pathlib import Path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def iso(ts: dt.datetime) -> str:
    # SQLite DATETIME 문자열(로컬 타임)로 저장
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def date_only(d: dt.date) -> str:
    return d.strftime("%Y-%m-%d")


def daterange(start: dt.date, end_inclusive: dt.date):
    d = start
    while d <= end_inclusive:
        yield d
        d += dt.timedelta(days=1)


def ensure_dirs(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


def apply_schema(conn: sqlite3.Connection, schema_sql: str) -> None:
    conn.executescript(schema_sql)
    conn.commit()


def upsert_zone(conn: sqlite3.Connection, code: str, name: str) -> int:
    conn.execute(
        "INSERT OR IGNORE INTO zones(zone_code, zone_name) VALUES(?, ?)",
        (code, name),
    )
    row = conn.execute("SELECT id FROM zones WHERE zone_code=?", (code,)).fetchone()
    assert row is not None
    return int(row[0])


def upsert_device(conn: sqlite3.Connection, device_code: str, device_type: str, device_name: str, zone_id: int | None) -> int:
    conn.execute(
        """
        INSERT OR IGNORE INTO devices(device_code, device_type, device_name, zone_id, is_active)
        VALUES(?, ?, ?, ?, 1)
        """,
        (device_code, device_type, device_name, zone_id),
    )
    row = conn.execute("SELECT id FROM devices WHERE device_code=?", (device_code,)).fetchone()
    assert row is not None
    return int(row[0])


def seed_schedules(conn: sqlite3.Connection, led_device_ids: list[int]) -> None:
    # LED 기본 스케줄: 08:00 ON / 17:00 OFF (향후 작물/계절/Bed별로 조정)
    for did in led_device_ids:
        conn.execute(
            """
            INSERT OR IGNORE INTO schedules(device_id, schedule_name, cron_expr, action, is_active)
            VALUES(?, ?, ?, ?, 1)
            """,
            (did, "기본 점등 ON", "0 8 * * *", "ON"),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO schedules(device_id, schedule_name, cron_expr, action, is_active)
            VALUES(?, ?, ?, ?, 1)
            """,
            (did, "기본 점등 OFF", "0 17 * * *", "OFF"),
        )


def seed_operation_logs(conn: sqlite3.Connection, led_device_ids: list[int], pump_device_ids: dict[str, int], start: dt.date, end: dt.date) -> None:
    """
    - LED: 매일 08:00~17:00 가동했다고 가정(스케줄)
    - Pump B1: 주간(08~20) 20초 ON / 4분40초 OFF 반복, 야간(20~08) 15초 ON / 9분45초 OFF 반복
    - 수동 ON/OFF 이벤트도 소량 섞어서 기록
    """
    tz = dt.timezone(dt.timedelta(hours=9))  # Asia/Seoul (단순화: 로컬 저장)

    def dt_at(d: dt.date, hh: int, mm: int, ss: int = 0) -> dt.datetime:
        return dt.datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=tz).replace(tzinfo=None)

    # LED 기본 로그
    for d in daterange(start, end):
        on = dt_at(d, 8, 0, 0)
        off = dt_at(d, 17, 0, 0)
        for did in led_device_ids:
            conn.execute(
                """
                INSERT INTO operation_logs(device_id, started_at, ended_at, duration_sec, trigger_type, trigger_reason, operator)
                VALUES(?, ?, ?, ?, 'schedule', 'default_led_schedule', 'system')
                """,
                (did, iso(on), iso(off), int((off - on).total_seconds())),
            )

    # Pump B1 반복 패턴 로그
    pb1 = pump_device_ids.get("pump_b1")
    if pb1:
        for d in daterange(start, end):
            day_start = dt_at(d, 0, 0, 0)
            day_end = day_start + dt.timedelta(days=1)
            t = day_start
            while t < day_end:
                is_day = (t.hour >= 8) and (t.hour < 20)
                on_s = 20 if is_day else 15
                off_s = (4 * 60 + 40) if is_day else (9 * 60 + 45)
                on = t
                off = min(t + dt.timedelta(seconds=on_s), day_end)
                conn.execute(
                    """
                    INSERT INTO operation_logs(device_id, started_at, ended_at, duration_sec, trigger_type, trigger_reason, operator)
                    VALUES(?, ?, ?, ?, 'schedule', 'cycle_pump_b1', 'system')
                    """,
                    (pb1, iso(on), iso(off), int((off - on).total_seconds())),
                )
                t = off + dt.timedelta(seconds=off_s)

    # 수동 조작 이벤트(가끔)
    rng = random.Random(42)
    all_devices = [*led_device_ids, *pump_device_ids.values()]
    for d in daterange(start, end):
        if rng.random() < 0.08:
            did = rng.choice(all_devices)
            hh = rng.choice([6, 7, 18, 19, 21])
            mm = rng.choice([0, 5, 10, 30, 45])
            dur = rng.choice([60, 120, 300])
            st = dt_at(d, hh, mm, 0)
            ed = st + dt.timedelta(seconds=dur)
            conn.execute(
                """
                INSERT INTO operation_logs(device_id, started_at, ended_at, duration_sec, trigger_type, trigger_reason, operator, notes)
                VALUES(?, ?, ?, ?, 'manual', 'operator_override', 'operator', '테스트: 수동 토글')
                """,
                (did, iso(st), iso(ed), int((ed - st).total_seconds())),
            )


def seed_weather_and_sensors(conn: sqlite3.Connection, zone_a: int, zone_b: int, start: dt.date, end: dt.date) -> None:
    """
    테스트용 센서/환경 시계열을 SQLite `sensor_readings`에 저장한다.
    - field: temp/humidity/co2/ph/ec
    - zone: zone_a/zone_b
    - sensor_id: 'sensor_01'
    - source: 'seed'
    """
    rng = random.Random(7)
    # 재실행 안전: 시드가 만든 구간은 지우고 다시 채움
    start_ts = dt.datetime(start.year, start.month, start.day, 0, 0, 0)
    end_ts = dt.datetime(end.year, end.month, end.day, 23, 59, 59)
    conn.execute(
        "DELETE FROM sensor_readings WHERE source='seed' AND observed_at BETWEEN ? AND ?",
        (iso(start_ts), iso(end_ts)),
    )

    def insert(sensor_id: str, zone_id: int, field: str, value: float, unit: str | None, observed_at: dt.datetime) -> None:
        conn.execute(
            """
            INSERT INTO sensor_readings(sensor_id, zone_id, field, value, unit, observed_at, source)
            VALUES(?, ?, ?, ?, ?, ?, 'seed')
            """,
            (sensor_id, zone_id, field, float(value), unit, iso(observed_at)),
        )

    for d in daterange(start, end):
        # 일변화(외부기온): 사인 기반 + 랜덤
        day_of_year = d.timetuple().tm_yday
        base_temp = 12.0 + 8.0 * math.sin((day_of_year / 365.0) * 2.0 * math.pi)
        temp_min = base_temp - 4.0 + rng.uniform(-0.8, 0.8)
        temp_max = base_temp + 6.0 + rng.uniform(-0.8, 0.8)

        # 30분 간격으로 시계열 생성(주: 로컬 naive로 저장)
        for hh in range(0, 24):
            for mm in (0, 30):
                t = dt.datetime(d.year, d.month, d.day, hh, mm, 0)
                # 0~1
                x = (hh * 60 + mm) / (24.0 * 60.0)
                # 내부 온도(외부 기반 + 약간의 완충)
                temp = (temp_min + (temp_max - temp_min) * math.sin(x * math.pi)) + rng.uniform(-0.4, 0.4)
                # 습도(온도와 약간 반비례)
                humidity = 72.0 - (temp - 18.0) * 1.2 + rng.uniform(-2.0, 2.0)
                humidity = max(35.0, min(95.0, humidity))
                # CO2 (주간 상승)
                co2 = 850.0 + (200.0 if 8 <= hh < 20 else 60.0) + rng.uniform(-40.0, 40.0)
                co2 = max(400.0, min(2000.0, co2))
                # pH/EC (완만한 변동)
                ph = 6.6 + 0.15 * math.sin(x * 2.0 * math.pi) + rng.uniform(-0.05, 0.05)
                ec = 2.2 + 0.35 * math.sin((x + 0.15) * 2.0 * math.pi) + rng.uniform(-0.08, 0.08)
                ec = max(0.8, min(3.6, ec))

                # zone_a, zone_b 각각 저장(조금 다르게)
                insert("sensor_01", zone_a, "temp", temp + 0.3, "celsius", t)
                insert("sensor_01", zone_a, "humidity", humidity, "percent", t)
                insert("sensor_01", zone_a, "co2", co2, "ppm", t)
                insert("sensor_01", zone_a, "ph", ph, "none", t)
                insert("sensor_01", zone_a, "ec", ec, "mS/cm", t)

                insert("sensor_01", zone_b, "temp", temp - 0.2, "celsius", t)
                insert("sensor_01", zone_b, "humidity", max(35.0, min(95.0, humidity + rng.uniform(-1.5, 1.5))), "percent", t)
                insert("sensor_01", zone_b, "co2", max(400.0, min(2000.0, co2 + rng.uniform(-30.0, 30.0))), "ppm", t)
                insert("sensor_01", zone_b, "ph", ph + rng.uniform(-0.06, 0.06), "none", t)
                insert("sensor_01", zone_b, "ec", max(0.8, min(3.6, ec + rng.uniform(-0.12, 0.12))), "mS/cm", t)

        # pH/EC 범위이탈 이벤트를 가끔 생성
        if rng.random() < 0.06:
            ph = 5.7 if rng.random() < 0.5 else 8.1
            thr = 6.0 if ph < 6.0 else 8.0
            sev = "warning"
            msg = f"pH 범위 이탈 ({ph:.1f})"
            occurred = dt.datetime(d.year, d.month, d.day, 8, 30, 0)
            conn.execute(
                """
                INSERT INTO alert_events(alert_type, severity, source, zone_id, message, value_actual, value_threshold, occurred_at, notify_channel, notify_sent)
                VALUES('sensor_out_of_range', ?, 'sensor_01', ?, ?, ?, ?, ?, 'telegram', 1)
                """,
                (sev, zone_a, msg, ph, thr, iso(occurred)),
            )
        if rng.random() < 0.05:
            ec = 3.2 if rng.random() < 0.5 else 1.2
            thr = 3.0 if ec > 3.0 else 1.5
            sev = "warning"
            msg = f"EC 범위 이탈 ({ec:.1f} mS/cm)"
            occurred = dt.datetime(d.year, d.month, d.day, 9, 10, 0)
            conn.execute(
                """
                INSERT INTO alert_events(alert_type, severity, source, zone_id, message, value_actual, value_threshold, occurred_at, notify_channel, notify_sent)
                VALUES('sensor_out_of_range', ?, 'sensor_01', ?, ?, ?, ?, ?, 'telegram', 1)
                """,
                (sev, zone_b, msg, ec, thr, iso(occurred)),
            )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="생성/갱신할 SQLite DB 파일 경로")
    ap.add_argument("--schema", required=True, help="smartfarm_schema.sql 경로")
    ap.add_argument("--start", default="2026-04-01", help="시드 시작일(YYYY-MM-DD)")
    ap.add_argument("--end", default=None, help="시드 종료일(YYYY-MM-DD), 기본: 오늘")
    ap.add_argument("--reset", action="store_true", help="기존 DB가 있으면 삭제 후 재생성")
    args = ap.parse_args()

    db_path = Path(args.db)
    schema_path = Path(args.schema)
    if args.reset and db_path.exists():
        db_path.unlink()
    ensure_dirs(db_path)

    start_d = dt.date.fromisoformat(args.start)
    end_d = dt.date.fromisoformat(args.end) if args.end else dt.date.today()

    schema_sql = read_text(schema_path)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        apply_schema(conn, schema_sql)

        # 기본 존/장치 등록
        zone_a = upsert_zone(conn, "zone_a", "재배동 A구역")
        zone_b = upsert_zone(conn, "zone_b", "재배동 B구역")

        led_ids: list[int] = []
        # Bed/채널은 향후 확장. 우선 대표 LED 3개
        led_ids.append(upsert_device(conn, "led_a1", "led", "LED A1", zone_a))
        led_ids.append(upsert_device(conn, "led_a2", "led", "LED A2", zone_a))
        led_ids.append(upsert_device(conn, "led_b1", "led", "LED B1", zone_b))

        pump_ids = {
            "pump_b1": upsert_device(conn, "pump_b1", "pump", "Pump B1", zone_b),
        }

        seed_schedules(conn, led_ids)
        seed_operation_logs(conn, led_ids, pump_ids, start_d, end_d)
        seed_weather_and_sensors(conn, zone_a, zone_b, start_d, end_d)

        conn.commit()
        print(f"완료: DB 생성/시딩 -> {db_path}")
        print(f"- 기간: {date_only(start_d)} ~ {date_only(end_d)}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

