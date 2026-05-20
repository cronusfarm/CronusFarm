#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CronusFarm DB 시드: SQLite 스키마 + Influx 시계열 + Open-Meteo(서울) 시간별 외기.
외기: ECMWF 등 재분석 격자(Open-Meteo Archive). 공식 기상청 ASOS 원시와 동일하지 않을 수 있음.
내부/액추에이터/카메라: 2026-04-01 ~ 04-23 임의 시계열.
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))

# Open-Meteo: 서울 근처
LAT, LON = 37.57, 126.98
OPEN_METEO_URL = (
    "https://archive-api.open-meteo.com/v1/archive"
    "?latitude={lat}&longitude={lon}"
    "&start_date={sd}&end_date={ed}"
    "&hourly=temperature_2m,relative_humidity_2m,precipitation,"
    "wind_speed_10m,wind_direction_10m,wind_gusts_10m"
    "&timezone=Asia%2FSeoul"
)

INFLUX_METRICS_PURGE = (
    "external_weather",
    "internal_rs485",
    "actuator_duty",
    "camera_event",
)

ACT_KEYS = ("led_a1", "led_b1", "led_b2", "pump_a1", "pump_a2", "pump_b1", "pump_b2")
RS485_METRICS = ("ec", "tds", "cf", "ph", "orp", "temp", "hum")


def epoch_kst(y: int, m: int, d: int, hh: int = 0, mm: int = 0) -> int:
    return int(datetime(y, m, d, hh, mm, tzinfo=KST).timestamp())


def iso_kst(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=KST).strftime("%Y-%m-%dT%H:%M:%S%z")


def fetch_open_meteo(start_date: str, end_date: str) -> dict:
    url = OPEN_METEO_URL.format(lat=LAT, lon=LON, sd=start_date, ed=end_date)
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def influx_write(
    base: str,
    db: str,
    user: str,
    password: str,
    lines: list[str],
    batch: int = 400,
) -> None:
    for i in range(0, len(lines), batch):
        chunk = "\n".join(lines[i : i + batch]) + "\n"
        req = urllib.request.Request(
            f"{base}/write?db={db}&u={user}&p={password}&precision=s",
            data=chunk.encode("utf-8"),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                if resp.status not in (200, 204):
                    raise RuntimeError(f"Influx HTTP {resp.status}")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Influx write 실패: {e} {body}") from e


def influx_purge_range(
    host: str,
    port: int,
    db: str,
    user: str,
    password: str,
    t0: int,
    t1: int,
) -> None:
    """InfluxDB 1.x: DELETE FROM ... WHERE time >= t0s AND time < t1s (epoch 초)."""
    base = f"http://{host}:{port}"
    for m in INFLUX_METRICS_PURGE:
        q = f"DELETE FROM \"{m}\" WHERE time >= {t0}s AND time < {t1}s"
        url = f"{base}/query?db={db}&u={user}&p={password}&q=" + urllib.parse.quote(q)
        req = urllib.request.Request(url, method="POST")
        with urllib.request.urlopen(req, timeout=60) as resp:
            resp.read()


def apply_sqlite_schema(conn: sqlite3.Connection, schema_path: Path) -> None:
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    conn.commit()


def seed_sqlite_beds(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("DELETE FROM crop_assignment")
    cur.execute("DELETE FROM bed_layer")
    cur.execute("DELETE FROM bed")
    beds = [
        ("A", "A Bed", 10, [(1, "1층"), (2, "2층")]),
        ("B", "B Bed", 20, [(1, "1층"), (2, "2층"), (3, "3층")]),
        ("C", "C Bed", 30, [(1, "1층")]),
    ]
    crops = {
        ("A", 1): ("상추", "적상추", "2026-03-15", "2026-05-10"),
        ("A", 2): ("케일", "베이비케일", "2026-03-20", "2026-05-20"),
        ("B", 1): ("딸기", "설향", "2026-02-01", "2026-06-30"),
        ("B", 2): ("바질", "제노베제", "2026-04-01", "2026-06-01"),
        ("B", 3): ("방울토마토", "초코토마토", "2026-04-05", "2026-08-01"),
        ("C", 1): ("(미정)", None, None, None),
    }
    for code, name, order, layers in beds:
        cur.execute(
            "INSERT INTO bed (code, name, sort_order) VALUES (?,?,?)",
            (code, name, order),
        )
        bid = cur.lastrowid
        for lno, lab in layers:
            cur.execute(
                "INSERT INTO bed_layer (bed_id, layer_no, label) VALUES (?,?,?)",
                (bid, lno, lab),
            )
            lid = cur.lastrowid
            key = (code, lno)
            if key in crops:
                sp, va, pd, eh = crops[key]
                cur.execute(
                    """INSERT INTO crop_assignment
                    (bed_layer_id, species, variety, planted_date, expected_harvest, notes)
                    VALUES (?,?,?,?,?,?)""",
                    (lid, sp, va, pd, eh, "시드 데이터"),
                )
    conn.commit()


def seed_camera_sqlite(conn: sqlite3.Connection, year: int, rng: random.Random) -> None:
    cur = conn.cursor()
    cur.execute("DELETE FROM camera_recording")
    for d in range(1, 24):
        for slot, bed in enumerate(("A", "B", "A")):
            h = 9 + slot * 5
            ts_iso = datetime(year, 4, d, h, 10, tzinfo=KST).strftime("%Y-%m-%dT%H:%M:%S")
            fname = f"{year}04{d:02d}_{h:02d}00_cam{slot}.mp4"
            path = f"/var/lib/cronusfarm/cam/{fname}"
            dur = rng.choice((180, 300, 600))
            sz = round(rng.uniform(12, 180), 2)
            cur.execute(
                """INSERT INTO camera_recording
                (bed_code, layer_no, file_path, started_at, duration_sec, size_mb, notes)
                VALUES (?,?,?,?,?,?,?)""",
                (bed, 1 if bed == "C" else slot + 1, path, ts_iso, dur, sz, "시드"),
            )
    conn.commit()


def seed_weather_sqlite(
    conn: sqlite3.Connection,
    times: list[str],
    rows: dict[str, list],
) -> None:
    cur = conn.cursor()
    cur.execute("DELETE FROM weather_obs_hourly")
    t_arr = rows["temperature_2m"]
    rh = rows["relative_humidity_2m"]
    pr = rows["precipitation"]
    ws = rows["wind_speed_10m"]
    wd = rows["wind_direction_10m"]
    wg = rows["wind_gusts_10m"]
    for i, tt in enumerate(times):
        wsk = float(ws[i])  # km/h
        wgk = float(wg[i])
        w_ms = round(wsk / 3.6, 3)
        g_ms = round(wgk / 3.6, 3)
        run_km = round(wsk * 1.0, 3)
        cur.execute(
            """INSERT INTO weather_obs_hourly
            (obs_time, temp_c, rh_pct, rain_mm, wind_speed_ms, wind_gust_ms, wind_dir_deg, wind_run_km, source)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                tt,
                float(t_arr[i]),
                float(rh[i]),
                float(pr[i]),
                w_ms,
                g_ms,
                float(wd[i]),
                run_km,
                "open_meteo_archive_seoul",
            ),
        )
    conn.commit()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sqlite", default="/home/dooly/CronusFarm/data/cronusfarm.sqlite")
    ap.add_argument("--schema", default=None, help="sqlite_schema.sql 경로")
    ap.add_argument("--influx-host", default="127.0.0.1")
    ap.add_argument("--influx-port", type=int, default=8086)
    ap.add_argument("--influx-db", default="cronusfarm")
    ap.add_argument("--influx-user", default="cronusfarm")
    ap.add_argument("--influx-pass", default="cronusfarm1234")
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--purge-influx", action="store_true", help="지정 구간 Influx 시드 measurement 삭제 후 재삽입")
    args = ap.parse_args()

    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    schema = Path(args.schema) if args.schema else repo_root / "db" / "sqlite_schema.sql"
    if not schema.is_file():
        print("스키마 파일 없음:", schema, file=sys.stderr)
        return 1

    t_start = epoch_kst(args.year, 4, 1, 0, 0)
    t_end = epoch_kst(args.year, 4, 24, 0, 0)

    sqlite_path = Path(args.sqlite)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(sqlite_path))
    apply_sqlite_schema(conn, schema)
    seed_sqlite_beds(conn)

    print("[INFO] Open-Meteo(서울) 시간별 외기 수집…")
    data = fetch_open_meteo(f"{args.year}-04-01", f"{args.year}-04-23")
    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []
    if not times:
        print("Open-Meteo 응답에 hourly.time 없음", file=sys.stderr)
        return 1

    seed_weather_sqlite(conn, times, hourly)
    rng = random.Random(202604)
    seed_camera_sqlite(conn, args.year, rng)

    influx_base = f"http://{args.influx_host}:{args.influx_port}"
    lines: list[str] = []

    for i, tt in enumerate(times):
        dt = datetime.fromisoformat(tt)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=KST)
        ts = int(dt.timestamp())
        temp = float(hourly["temperature_2m"][i])
        rh = float(hourly["relative_humidity_2m"][i])
        rain = float(hourly["precipitation"][i])
        wsk = float(hourly["wind_speed_10m"][i])
        wgk = float(hourly["wind_gusts_10m"][i])
        wdir = float(hourly["wind_direction_10m"][i])
        w_ms = round(wsk / 3.6, 4)
        g_ms = round(wgk / 3.6, 4)
        run_km = round(wsk * 1.0, 4)
        lines.append(
            "external_weather,location=seoul,source=open_meteo_archive "
            f"temp_c={temp},rh_pct={rh},rain_mm={rain},wind_speed_ms={w_ms},"
            f"wind_gust_ms={g_ms},wind_dir_deg={wdir},wind_run_km={run_km} {ts}"
        )

    # 내부 RS485: 10분 간격
    cur_ts = t_start
    _base = {"ec": 1.4, "tds": 820.0, "cf": 0.9, "ph": 6.1, "orp": 310.0, "temp": 22.5, "hum": 62.0}
    state = {m: _base[m] for m in RS485_METRICS}
    while cur_ts < t_end:
        for metric in RS485_METRICS:
            v = float(state[metric])
            dv = (rng.random() - 0.5) * {"ec": 0.04, "tds": 30, "cf": 0.02, "ph": 0.05, "orp": 10, "temp": 0.4, "hum": 1.5}[metric]
            v = v + dv
            clamps = {"ec": (0.6, 2.8), "tds": (400, 1500), "cf": (0.5, 2.0), "ph": (5.4, 6.9), "orp": (180, 450), "temp": (18, 29), "hum": (38, 92)}
            lo, hi = clamps[metric]
            v = max(lo, min(hi, v))
            state[metric] = v
            lines.append(
                f"internal_rs485,device=3178,metric={metric} value={round(v, 4)} {cur_ts}"
            )
        cur_ts += 600

    # 액추에이터 duty: 매 정시 구간 [ts, ts+3600)
    for ts in range(t_start, t_end, 3600):
        for key in ACT_KEYS:
            on = rng.randint(600, 3000) if key.startswith("pump") else rng.randint(1200, 3200)
            on = min(on, 3500)
            off = max(0, 3600 - on)
            lines.append(f"actuator_duty,key={key} on_sec={on},off_sec={off} {ts}")

    # 카메라: 하루 2건 가량
    for d in range(1, 24):
        day0 = epoch_kst(args.year, 4, d, 0, 0)
        for slot, bed in enumerate(("A", "B", "A")):
            h = 9 + slot * 5
            ts = epoch_kst(args.year, 4, d, h, 10)
            fname = f"{args.year}04{d:02d}_{h:02d}00_cam{slot}.mp4"
            dur = rng.choice((180, 300, 600))
            sz = round(rng.uniform(12, 180), 2)
            lines.append(
                f"camera_event,bed_code={bed},camera_id=cam{slot},file={fname} "
                f"duration_sec={dur}i,size_mb={sz} {ts}"
            )

    if args.purge_influx:
        print("[INFO] Influx 구간 삭제:", iso_kst(t_start), "~", iso_kst(t_end))
        influx_purge_range(
            args.influx_host,
            args.influx_port,
            args.influx_db,
            args.influx_user,
            args.influx_pass,
            t_start,
            t_end,
        )

    print("[INFO] Influx 라인 기록:", len(lines))
    influx_write(
        influx_base,
        args.influx_db,
        args.influx_user,
        args.influx_pass,
        lines,
    )

    conn.close()
    print("[OK] SQLite:", sqlite_path)
    print("[OK] Influx 완료 (external_weather, internal_rs485, actuator_duty, camera_event)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
