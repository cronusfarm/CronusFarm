#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KMA 초단기실황 즉시 조회 → MQTT cronusfarm/kma/snapshot (retain)."""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))
NCST_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
# 자외선: 기상청 생활기상지수(3.0) — B552584 경로는 500 오류
UV_URL = "https://apis.data.go.kr/1360000/LivingWthrIdxServiceV4/getUVIdxV4"
# 미세먼지: 에어코리아 시도별 실시간(측정소명 403 시 폴백)
PM_STATION_URL = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty"
PM_SIDO_URL = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty"


def load_env() -> dict[str, str]:
    out = dict(os.environ)
    dropin = Path("/etc/systemd/system/nodered.service.d")
    if dropin.is_dir():
        for conf in sorted(dropin.glob("*.conf")):
            text = conf.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                if line.strip().startswith("Environment="):
                    raw = line.strip()[len("Environment=") :].strip().strip('"')
                    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", raw)
                    if m:
                        out[m.group(1)] = m.group(2)
    for p in ("/etc/cronusfarm/nodered-telegram.env",):
        try:
            with open(p, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip().strip("'\"")
        except OSError:
            pass
    return out


def kst_base() -> tuple[str, str]:
    now = datetime.now(KST)
    y, mo, d, hh, mm = now.year, now.month, now.day, now.hour, now.minute
    if mm < 40:
        now = now - timedelta(hours=1)
        y, mo, d, hh = now.year, now.month, now.day, now.hour
    return f"{y:04d}{mo:02d}{d:02d}", f"{hh:02d}00"


def num(v):
    try:
        n = float(v)
        return n if n == n else None
    except (TypeError, ValueError):
        return None


def fetch_json(url: str, params: dict) -> dict | None:
    qs = urllib.parse.urlencode(params)
    full = f"{url}?{qs}" if qs else url
    return fetch_url_json(full)


def fetch_url_json(full_url: str) -> dict | None:
    req = urllib.request.Request(
        full_url,
        headers={"User-Agent": "CronusFarm/kma-refresh"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        tag = full_url.split("?")[0].split("/")[-1] or "http"
        print(f"WARN: {tag} — {exc}", file=sys.stderr)
        return None


def _api_items(body: dict | None) -> list:
    if not body:
        return []
    items = body.get("response", {}).get("body", {}).get("items")
    if isinstance(items, dict):
        sub = items.get("item")
        if isinstance(sub, list):
            return sub
        if isinstance(sub, dict):
            return [sub]
        return [items] if items else []
    if isinstance(items, list):
        return items
    return []


def fetch_uv_index(key: str, area_no: str) -> float | None:
    now = datetime.now(KST)
    ymdh = now.strftime("%Y%m%d%H")
    for area in [a.strip() for a in area_no.split(",") if a.strip()]:
        body = fetch_json(
            UV_URL,
            {
                "serviceKey": key,
                "pageNo": "1",
                "numOfRows": "10",
                "dataType": "JSON",
                "areaNo": area,
                "time": ymdh,
            },
        )
        items = _api_items(body)
        if not items:
            continue
        best = sorted(items, key=lambda x: str(x.get("h0", x.get("today", ""))), reverse=True)[0]
        for field in ("h0", "today", "h1", "uvIdx", "value"):
            v = num(best.get(field))
            if v is not None:
                return v
    return None


def fetch_pm10_station(key: str, stations: str) -> tuple[float | None, str | None]:
    for station in [s.strip() for s in stations.split(",") if s.strip()]:
        body = fetch_json(
            PM_STATION_URL,
            {
                "serviceKey": key,
                "returnType": "json",
                "numOfRows": "1",
                "pageNo": "1",
                "stationName": station,
                "dataTerm": "DAILY",
                "ver": "1.3",
            },
        )
        items = _api_items(body)
        if not items:
            continue
        row = items[0]
        pm = num(row.get("pm10Value"))
        if pm is None:
            continue
        grade = str(row.get("pm10Grade") or "").strip() or None
        return pm, grade
    return None, None


def fetch_pm10_sido(key: str, sido: str) -> tuple[float | None, str | None]:
    body = fetch_json(
        PM_SIDO_URL,
        {
            "serviceKey": key,
            "returnType": "json",
            "numOfRows": "100",
            "pageNo": "1",
            "sidoName": sido,
            "ver": "1.3",
        },
    )
    items = _api_items(body)
    for row in items:
        if not isinstance(row, dict):
            continue
        pm = num(row.get("pm10Value"))
        if pm is None:
            continue
        grade = str(row.get("pm10Grade1") or row.get("pm10Grade") or "").strip() or None
        return pm, grade
    return None, None


def fetch_pm10(key: str, stations: str, sido: str) -> tuple[float | None, str | None]:
    pm, grade = fetch_pm10_station(key, stations)
    if pm is not None:
        return pm, grade
    return fetch_pm10_sido(key, sido)


def pm10_grade_kr(pm: float) -> str:
    if pm <= 30:
        return "1"
    if pm <= 80:
        return "2"
    if pm <= 150:
        return "3"
    return "4"


def fetch_openmeteo_uv_pm(lat: float, lon: float) -> tuple[float | None, float | None, str | None]:
    """KMA 생활기상/에어코리아 키 미승인 시 Open-Meteo 폴백(위경도)."""
    uv = None
    pm = None
    grade = None
    q_uv = urllib.parse.urlencode(
        {
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "current": "uv_index",
            "timezone": "Asia/Seoul",
        }
    )
    body = fetch_url_json(f"https://api.open-meteo.com/v1/forecast?{q_uv}")
    cur = (body or {}).get("current") or {}
    uv = num(cur.get("uv_index"))
    q_pm = urllib.parse.urlencode(
        {
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "hourly": "pm10,pm2_5",
            "timezone": "Asia/Seoul",
            "forecast_hours": "1",
        }
    )
    body2 = fetch_url_json(f"https://air-quality-api.open-meteo.com/v1/air-quality?{q_pm}")
    hourly = (body2 or {}).get("hourly") or {}
    pm_list = hourly.get("pm10") or []
    for v in pm_list:
        pm = num(v)
        if pm is not None:
            grade = pm10_grade_kr(pm)
            break
    return uv, pm, grade


def main() -> int:
    env = load_env()
    key = env.get("CRONUSFARM_KMA_SERVICE_KEY", "").strip()
    nx = int(env.get("CRONUSFARM_KMA_NX", "0") or "0")
    ny = int(env.get("CRONUSFARM_KMA_NY", "0") or "0")
    if not key or not nx or not ny:
        print("ERROR: KMA key or nx/ny missing", file=sys.stderr)
        return 1
    bd, bt = kst_base()
    qs = urllib.parse.urlencode(
        {
            "serviceKey": key,
            "numOfRows": "60",
            "pageNo": "1",
            "dataType": "JSON",
            "base_date": bd,
            "base_time": bt,
            "nx": str(nx),
            "ny": str(ny),
        }
    )
    url = f"{NCST_URL}?{qs}"
    with urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "CronusFarm/kma-refresh"}),
        timeout=30,
    ) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    items = body.get("response", {}).get("body", {}).get("items", {}).get("item", [])
    if not isinstance(items, list):
        print("ERROR: no KMA items", body, file=sys.stderr)
        return 1
    m = {str(it.get("category")): str(it.get("obsrValue", "")) for it in items}
    pty = num(m.get("PTY"))
    rn1 = num(m.get("RN1"))
    # nx=71,ny=127(수도권 서부) 기본: 안양 행정구역·인근 측정소
    area_no = env.get("CRONUSFARM_KMA_UV_AREA_NO", "4117300000,4111100000,1100000000").strip()
    air_station = env.get("CRONUSFARM_AIR_STATION", "안양,군포,수원,중구").strip()
    air_sido = env.get("CRONUSFARM_AIR_SIDO", "경기").strip()
    uv = fetch_uv_index(key, area_no)
    pm10, pm_grade = fetch_pm10(key, air_station, air_sido)
    if uv is None or pm10 is None:
        try:
            lat = float(env.get("CRONUSFARM_FARM_LAT", "37.39"))
            lon = float(env.get("CRONUSFARM_FARM_LON", "126.95"))
        except ValueError:
            lat, lon = 37.39, 126.95
        om_uv, om_pm, om_grade = fetch_openmeteo_uv_pm(lat, lon)
        if uv is None:
            uv = om_uv
        if pm10 is None:
            pm10, pm_grade = om_pm, om_grade

    snap = {
        "kma_temp": num(m.get("T1H")),
        "kma_humidity": num(m.get("REH")),
        "kma_wind_dir": num(m.get("VEC")),
        "kma_wind_speed": num(m.get("WSD")),
        "kma_pty": pty,
        "kma_precip_type": pty,
        "kma_precip_1h": rn1,
        "kma_uv_index": uv,
        "kma_pm10": pm10,
        "kma_pm10_grade": pm_grade,
        "base_date": bd,
        "base_time": bt,
        "nx": nx,
        "ny": ny,
        "ts": int(time.time() * 1000),
    }
    print("KMA snap:", json.dumps(snap, ensure_ascii=False))

    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("WARN: paho-mqtt 없음 — snap만 출력", file=sys.stderr)
        return 0

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        client = mqtt.Client()
    client.connect("127.0.0.1", 1883, 60)
    client.publish(
        "cronusfarm/kma/snapshot",
        json.dumps(snap, ensure_ascii=False),
        qos=0,
        retain=True,
    )
    client.disconnect()
    print("OK published cronusfarm/kma/snapshot")
    return 0


if __name__ == "__main__":
    sys.exit(main())
