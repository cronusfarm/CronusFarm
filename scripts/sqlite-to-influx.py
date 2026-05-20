#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite(smartfarm.sqlite) → InfluxDB v2 버킷(CronusFarm) 미러링(테스트용).

- 목적: Grafana에서 "DB 기반 데이터"를 Influx(Flux)로 조회 가능하게 만든다.
- 특징:
  - idempotent(재실행 안전): sqlite_id 태그로 구분
  - state timeline을 위해 started_at(ON=1), ended_at(OFF=0) 이벤트를 모두 적재
  - duration/알람/스케줄/센서는 별도 measurement로 적재
"""

from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
import subprocess
from pathlib import Path


def parse_sqlite_dt(s: str) -> dt.datetime:
    # seed 스크립트가 "YYYY-MM-DD HH:MM:SS" 로 저장
    return dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def to_rfc3339(ts: dt.datetime) -> str:
    # Influx CLI는 RFC3339를 잘 받는다. (KST를 강제하지 않고 로컬 naive를 +09:00로 취급)
    # Pi는 Asia/Seoul이므로 naive도 로컬로 해석될 가능성이 있으나, 안전하게 +09:00을 붙인다.
    return ts.strftime("%Y-%m-%dT%H:%M:%S+09:00")


def lp_escape_tag(v: str) -> str:
    return v.replace("\\", "\\\\").replace(",", "\\,").replace(" ", "\\ ").replace("=", "\\=")


def lp_escape_measurement(v: str) -> str:
    return v.replace("\\", "\\\\").replace(",", "\\,").replace(" ", "\\ ")


def lp_escape_field_str(v: str) -> str:
    return v.replace("\\", "\\\\").replace('"', '\\"')


def influx_write(lines: list[str], bucket: str, org: str) -> None:
    if not lines:
        return
    payload = "\n".join(lines) + "\n"
    # influx CLI는 현재 사용자 컨텍스트(토큰/URL)를 이미 갖고 있는 상태라 가정.
    subprocess.run(
        ["influx", "write", "--org", org, "--bucket", bucket, "--precision", "s"],
        input=payload.encode("utf-8"),
        check=True,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sqlite", required=True, help="SQLite DB 경로 (smartfarm.sqlite)")
    ap.add_argument("--org", default="CronusFarm", help="Influx org")
    ap.add_argument("--bucket", default="CronusFarm", help="Influx bucket")
    ap.add_argument("--since", default="2026-04-01", help="이 날짜(YYYY-MM-DD) 이후만 미러링")
    args = ap.parse_args()

    sqlite_path = Path(args.sqlite)
    if not sqlite_path.exists():
        raise SystemExit(f"SQLite DB 없음: {sqlite_path}")

    since_dt = dt.datetime.fromisoformat(args.since + " 00:00:00")

    con = sqlite3.connect(str(sqlite_path))
    con.row_factory = sqlite3.Row
    try:
        # device 메타(코드/타입/존)
        dev_rows = con.execute(
            """
            SELECT d.id, d.device_code, d.device_type, z.zone_code
            FROM devices d
            LEFT JOIN zones z ON z.id = d.zone_id
            """
        ).fetchall()
        dev = {int(r["id"]): r for r in dev_rows}

        # 1) operation_logs → device_state 이벤트(ON/OFF) + duration
        op_rows = con.execute(
            """
            SELECT id, device_id, started_at, ended_at, duration_sec, trigger_type, trigger_reason, operator, set_value
            FROM operation_logs
            WHERE started_at >= ?
            ORDER BY started_at ASC
            """,
            (since_dt.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchall()

        state_lines: list[str] = []
        dur_lines: list[str] = []

        for r in op_rows:
            did = int(r["device_id"])
            meta = dev.get(did)
            if not meta:
                continue
            device_code = str(meta["device_code"])
            device_type = str(meta["device_type"])
            zone_code = str(meta["zone_code"]) if meta["zone_code"] is not None else "none"

            sid = int(r["id"])
            trig = str(r["trigger_type"])

            started = parse_sqlite_dt(r["started_at"])
            ended = parse_sqlite_dt(r["ended_at"]) if r["ended_at"] else None
            duration = int(r["duration_sec"]) if r["duration_sec"] is not None else None

            # state: ON 이벤트
            m = lp_escape_measurement("device_state")
            tags = (
                f"sqlite_id={sid},device={lp_escape_tag(device_code)},type={lp_escape_tag(device_type)},"
                f"zone={lp_escape_tag(zone_code)},trigger={lp_escape_tag(trig)}"
            )
            fields_on = "value=1i"
            state_lines.append(f"{m},{tags} {fields_on} {int(started.timestamp())}")

            # state: OFF 이벤트(ended_at가 있으면)
            if ended is not None:
                fields_off = "value=0i"
                state_lines.append(f"{m},{tags} {fields_off} {int(ended.timestamp())}")

            # duration: ended가 있을 때만 의미있게 기록
            if ended is not None and duration is not None:
                m2 = lp_escape_measurement("device_run")
                tags2 = (
                    f"sqlite_id={sid},device={lp_escape_tag(device_code)},type={lp_escape_tag(device_type)},"
                    f"zone={lp_escape_tag(zone_code)},trigger={lp_escape_tag(trig)}"
                )
                set_value = r["set_value"]
                fields = [f"duration_sec={duration}i"]
                if set_value is not None:
                    fields.append(f"set_value={float(set_value)}")
                dur_lines.append(f"{m2},{tags2} " + ",".join(fields) + f" {int(ended.timestamp())}")

        influx_write(state_lines, bucket=args.bucket, org=args.org)
        influx_write(dur_lines, bucket=args.bucket, org=args.org)

        # 2) alert_events → alerts measurement (문자 메시지는 string field)
        alert_rows = con.execute(
            """
            SELECT id, alert_type, severity, source, message, value_actual, value_threshold, occurred_at, resolved_at
            FROM alert_events
            WHERE occurred_at >= ?
            ORDER BY occurred_at ASC
            """,
            (since_dt.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchall()

        alert_lines: list[str] = []
        for r in alert_rows:
            aid = int(r["id"])
            t = parse_sqlite_dt(r["occurred_at"])
            m = lp_escape_measurement("alerts")
            tags = (
                f"sqlite_id={aid},type={lp_escape_tag(str(r['alert_type']))},"
                f"severity={lp_escape_tag(str(r['severity']))},source={lp_escape_tag(str(r['source']))}"
            )
            fields = [f"message=\"{lp_escape_field_str(str(r['message']))}\""]
            if r["value_actual"] is not None:
                fields.append(f"value_actual={float(r['value_actual'])}")
            if r["value_threshold"] is not None:
                fields.append(f"value_threshold={float(r['value_threshold'])}")
            # resolved 여부(0/1)
            fields.append(f"resolved={(1 if r['resolved_at'] else 0)}i")
            alert_lines.append(f"{m},{tags} " + ",".join(fields) + f" {int(t.timestamp())}")

        influx_write(alert_lines, bucket=args.bucket, org=args.org)

        # 3) schedules → schedules measurement (cron/action)
        sch_rows = con.execute(
            """
            SELECT s.id, d.device_code, d.device_type, z.zone_code, s.schedule_name, s.cron_expr, s.action, s.set_value, s.is_active
            FROM schedules s
            JOIN devices d ON d.id = s.device_id
            LEFT JOIN zones z ON z.id = d.zone_id
            ORDER BY s.id ASC
            """
        ).fetchall()

        sch_lines: list[str] = []
        now_ts = int(dt.datetime.now().timestamp())
        for r in sch_rows:
            sid = int(r["id"])
            m = lp_escape_measurement("schedules")
            zone_code = str(r["zone_code"]) if r["zone_code"] is not None else "none"
            tags = (
                f"sqlite_id={sid},device={lp_escape_tag(str(r['device_code']))},"
                f"type={lp_escape_tag(str(r['device_type']))},zone={lp_escape_tag(zone_code)},action={lp_escape_tag(str(r['action']))}"
            )
            fields = [
                f"is_active={int(r['is_active'])}i",
                f"name=\"{lp_escape_field_str(str(r['schedule_name']))}\"",
                f"cron=\"{lp_escape_field_str(str(r['cron_expr']))}\"",
            ]
            if r["set_value"] is not None:
                fields.append(f"set_value={float(r['set_value'])}")
            sch_lines.append(f"{m},{tags} " + ",".join(fields) + f" {now_ts}")

        influx_write(sch_lines, bucket=args.bucket, org=args.org)

        # 4) sensor_readings → tele_db measurement (환경/센서 시계열)
        # - Grafana 쿼리 패턴을 Influx의 tele(기존)와 유사하게 맞추기 위해 field/value 구조를 그대로 사용
        sr_rows = con.execute(
            """
            SELECT id, sensor_id, zone_id, field, value, unit, observed_at
            FROM sensor_readings
            WHERE observed_at >= ?
            ORDER BY observed_at ASC
            """,
            (since_dt.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchall()

        # zone_id → zone_code 매핑
        zone_rows = con.execute("SELECT id, zone_code FROM zones").fetchall()
        zones = {int(r["id"]): str(r["zone_code"]) for r in zone_rows}

        tele_lines: list[str] = []
        for r in sr_rows:
            rid = int(r["id"])
            sensor_id = str(r["sensor_id"])
            zone_id = int(r["zone_id"]) if r["zone_id"] is not None else None
            zone_code = zones.get(zone_id, "none") if zone_id is not None else "none"
            field = str(r["field"])
            value = float(r["value"])
            unit = str(r["unit"]) if r["unit"] is not None else "none"
            t = parse_sqlite_dt(r["observed_at"])

            m = lp_escape_measurement("tele_db")
            tags = f"sqlite_id={rid},sensor={lp_escape_tag(sensor_id)},zone={lp_escape_tag(zone_code)},unit={lp_escape_tag(unit)}"
            # Influx 필드키는 _field로 들어가므로 line protocol의 field key로 그대로 사용
            # 예: tele_db,sensor=sensor_01,zone=zone_a value=... 처럼 만들기 위해 field명을 field key로 쓴다.
            # 단, Grafana에서 tele처럼 _field 필터를 쓰려면 field key = temp/humidity/... 형태가 필요하다.
            fields = f"{lp_escape_tag(field)}={value}"
            tele_lines.append(f"{m},{tags} {fields} {int(t.timestamp())}")

        influx_write(tele_lines, bucket=args.bucket, org=args.org)

        print("완료: SQLite → Influx 미러링")
        print(f"- sqlite: {sqlite_path}")
        print(f"- org/bucket: {args.org}/{args.bucket}")
        print(f"- operation_logs: {len(op_rows)}")
        print(f"- alert_events: {len(alert_rows)}")
        print(f"- schedules: {len(sch_rows)}")
        print(f"- sensor_readings: {len(sr_rows)}")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())

