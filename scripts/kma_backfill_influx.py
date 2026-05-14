#!/usr/bin/env python3
"""
KMA → InfluxDB measurement `tele` (kma_* 필드) 백필.

- vilage (기본): 단기예보 getVilageFcst — API가 허용하는 **최근 약 3일** 구간만 채움(예보 값, 관측과 다를 수 있음).
- ncst: 초단기실황 getUltraSrtNcst — **최근 1일**만 제공(그 이전 시각은 resultCode 10).
- asos: ASOS 시간자료 — 장기 백필에 적합하나 공공데이터포털에서 **별도 활용신청**·엔드포인트가 맞아야 함.

Pi: systemd `nodered.service.d/*.conf` 의 Environment= 를 읽습니다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import defaultdict
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

ASOS_URL = "https://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList"
NCST_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
VILAGE_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
# 단기예보 발표 시각 (KST)
VILAGE_ISSUE_TIMES = ("0200", "0500", "0800", "1100", "1400", "1700", "2000", "2300")

DROPIN_GLOB = [
    "/etc/systemd/system/nodered.service.d/*.conf",
    str(Path.home() / ".config/systemd/user/nodered.service.d/*.conf"),
]


def load_env_from_dropins() -> dict[str, str]:
    out: dict[str, str] = {}
    import glob

    for pattern in DROPIN_GLOB:
        for path in sorted(glob.glob(pattern)):
            try:
                text = Path(path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line in text.splitlines():
                line = line.strip()
                if not line.startswith("Environment="):
                    continue
                raw = line[len("Environment=") :]
                if raw.startswith('"') and raw.endswith('"'):
                    raw = raw[1:-1]
                m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", raw)
                if m:
                    out[m.group(1)] = m.group(2)
    return out


def merge_env() -> dict[str, str]:
    e = {k: v for k, v in load_env_from_dropins().items() if v}
    e.update({k: v for k, v in os.environ.items() if v})
    return e


def http_get_json(url: str, sleep_s: float) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; CronusFarm/kma_backfill)"},
    )
    time.sleep(sleep_s)
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise SystemExit(f"JSON 파싱 실패(일부): {raw[:400]}")


def parse_kma_items(body: dict) -> list[dict]:
    items = body.get("response", {}).get("body", {}).get("items", {}).get("item")
    if items is None:
        return []
    if isinstance(items, dict):
        return [items]
    if isinstance(items, list):
        return items
    return []


def ncst_category_map(items: list[dict]) -> dict[str, str]:
    m: dict[str, str] = {}
    for it in items:
        cat = (it.get("category") or "").strip()
        val = it.get("obsrValue")
        if cat:
            m[cat] = str(val) if val is not None else ""
    return m


def num_or_none(v) -> float | None:
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def int_or_none(v) -> int | None:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def line_protocol_tele_kma(
    ts_ns: int,
    nx: int,
    ny: int,
    temp: float | None,
    hum: float | None,
    wdir: float | None,
    wspd: float | None,
    pty: int | None,
) -> str | None:
    fields: list[str] = []
    if temp is not None:
        fields.append(f"kma_temp={temp}")
    if hum is not None:
        fields.append(f"kma_humidity={hum}")
    if wdir is not None:
        fields.append(f"kma_wind_dir={wdir}")
    if wspd is not None:
        fields.append(f"kma_wind_speed={wspd}")
    if pty is not None:
        fields.append(f"kma_pty={pty}i")
    if not fields:
        return None
    tags = f"source=kma,nx={nx},ny={ny}"
    return f"tele,{tags} {','.join(fields)} {ts_ns}"


def influx_write(env: dict[str, str], line: str) -> None:
    token = env.get("CRONUSFARM_INFLUX_TOKEN", "").strip()
    org = urllib.parse.quote(env.get("CRONUSFARM_INFLUX_ORG", "cronusfarm").strip())
    bucket = urllib.parse.quote(env.get("CRONUSFARM_INFLUX_BUCKET", "cronusfarm").strip())
    base = env.get("CRONUSFARM_INFLUX_URL", "http://127.0.0.1:8086/api/v2/write").strip().rstrip("/")
    url = f"{base}?org={org}&bucket={bucket}&precision=ns"
    req = urllib.request.Request(
        url,
        data=line.encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Token {token}",
            "Content-Type": "text/plain; charset=utf-8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status not in (200, 204):
                raise SystemExit(f"Influx write HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:800]
        raise SystemExit(f"Influx write 실패 HTTP {e.code}: {body}") from e


def tm_to_ns_kst(tm: str) -> int | None:
    """ASOS item['tm'] 예: 202605011300 → KST 기준 나노초(UTC 저장)."""
    tm = str(tm).strip()
    if len(tm) >= 12:
        try:
            dt = datetime.strptime(tm[:12], "%Y%m%d%H%M").replace(tzinfo=KST)
            return int(dt.timestamp() * 1e9)
        except ValueError:
            return None
    return None


def backfill_asos(
    env: dict[str, str],
    stn_ids: str,
    start: datetime,
    end: datetime,
    sleep_s: float,
    dry_run: bool,
) -> tuple[int, int]:
    key = env.get("CRONUSFARM_KMA_SERVICE_KEY", "").strip()
    if not key:
        raise SystemExit("CRONUSFARM_KMA_SERVICE_KEY 없음")
    nx = int(env.get("CRONUSFARM_KMA_NX", "0") or "0")
    ny = int(env.get("CRONUSFARM_KMA_NY", "0") or "0")

    written = 0
    skipped = 0
    s = start.astimezone(KST)
    e = end.astimezone(KST)
    day = s.date()
    end_day = e.date()

    while day <= end_day:
        ymd = day.strftime("%Y%m%d")
        start_hh = s.strftime("%H") if day == s.date() else "00"
        end_hh = e.strftime("%H") if day == e.date() else "23"
        qs: dict[str, str] = {
            "serviceKey": key,
            "pageNo": "1",
            "numOfRows": "999",
            "dataType": "JSON",
            "dataCd": "ASOS",
            "dateCd": "HR",
            "startDt": ymd,
            "startHh": start_hh,
            "endDt": ymd,
            "endHh": end_hh,
            "stnIds": stn_ids,
        }
        page = 1
        nrows = int(qs["numOfRows"])
        while True:
            qs["pageNo"] = str(page)
            url = ASOS_URL + "?" + urllib.parse.urlencode(qs)
            data = http_get_json(url, sleep_s)
            hdr = data.get("response", {}).get("header", {})
            rc = str(hdr.get("resultCode", "")).strip()
            if rc and rc != "00":
                print(f"ASOS API 경고: {rc} {hdr.get('resultMsg', '')}", file=sys.stderr)
            items = parse_kma_items(data)
            if not items:
                break
            for it in items:
                tm = it.get("tm") or it.get("TM")
                ts_ns = tm_to_ns_kst(str(tm)) if tm else None
                if ts_ns is None:
                    skipped += 1
                    continue
                ta = num_or_none(it.get("TA") or it.get("ta") or it.get("avgTa") or it.get("AVGTA"))
                hm = num_or_none(it.get("HM") or it.get("hm"))
                ws = num_or_none(it.get("WS") or it.get("ws"))
                wd = num_or_none(it.get("WD") or it.get("wd"))
                pty = int_or_none(it.get("PTY") or it.get("pty"))
                line = line_protocol_tele_kma(ts_ns, nx, ny, ta, hm, wd, ws, pty)
                if not line:
                    skipped += 1
                    continue
                if dry_run:
                    print(line[:140] + ("..." if len(line) > 140 else ""))
                else:
                    influx_write(env, line)
                written += 1
            if len(items) < nrows:
                break
            page += 1
        day += timedelta(days=1)

    return written, skipped


def backfill_ncst(
    env: dict[str, str],
    start: datetime,
    end: datetime,
    step_hours: int,
    sleep_s: float,
    dry_run: bool,
) -> tuple[int, int]:
    key = env.get("CRONUSFARM_KMA_SERVICE_KEY", "").strip()
    nx = int(env.get("CRONUSFARM_KMA_NX", "0") or "0")
    ny = int(env.get("CRONUSFARM_KMA_NY", "0") or "0")
    if not key or not nx or not ny:
        raise SystemExit("KMA SERVICE_KEY 또는 NX/NY 없음")

    written = 0
    skipped = 0
    cur = start.astimezone(KST).replace(minute=0, second=0, microsecond=0)
    end_at = end.astimezone(KST).replace(minute=0, second=0, microsecond=0)

    while cur <= end_at:
        base_date = cur.strftime("%Y%m%d")
        base_time = cur.strftime("%H") + "00"
        qs = {
            "serviceKey": key,
            "numOfRows": "60",
            "pageNo": "1",
            "dataType": "JSON",
            "base_date": base_date,
            "base_time": base_time,
            "nx": str(nx),
            "ny": str(ny),
        }
        url = NCST_URL + "?" + urllib.parse.urlencode(qs)
        data = http_get_json(url, sleep_s)
        hdr = data.get("response", {}).get("header", {})
        rc = str(hdr.get("resultCode", "")).strip()
        if rc != "00":
            skipped += 1
            cur += timedelta(hours=step_hours)
            continue
        items = parse_kma_items(data)
        if not items:
            skipped += 1
            cur += timedelta(hours=step_hours)
            continue
        m = ncst_category_map(items)
        temp = num_or_none(m.get("T1H"))
        reh = num_or_none(m.get("REH"))
        vec = num_or_none(m.get("VEC"))
        wsd = num_or_none(m.get("WSD"))
        pty = int_or_none(m.get("PTY"))
        dt = datetime.strptime(base_date + base_time, "%Y%m%d%H%M").replace(tzinfo=KST)
        ts_ns = int(dt.timestamp() * 1e9)
        line = line_protocol_tele_kma(ts_ns, nx, ny, temp, reh, vec, wsd, pty)
        if line:
            if dry_run:
                print(line[:120])
            else:
                influx_write(env, line)
            written += 1
        else:
            skipped += 1
        cur += timedelta(hours=step_hours)

    return written, skipped


def fcst_datetime_kst(fcst_date: str, fcst_time: str) -> datetime:
    ft = str(fcst_time).strip().zfill(4)
    return datetime.strptime(str(fcst_date).strip() + ft, "%Y%m%d%H%M").replace(tzinfo=KST)


def backfill_vilage(
    env: dict[str, str],
    start: datetime,
    end: datetime,
    sleep_s: float,
    dry_run: bool,
) -> tuple[int, int]:
    """단기예보 격자값을 kma_* 로 적재(최근 3일 API 제한)."""
    key = env.get("CRONUSFARM_KMA_SERVICE_KEY", "").strip()
    nx = int(env.get("CRONUSFARM_KMA_NX", "0") or "0")
    ny = int(env.get("CRONUSFARM_KMA_NY", "0") or "0")
    if not key or not nx or not ny:
        raise SystemExit("KMA SERVICE_KEY 또는 NX/NY 없음")

    s = start.astimezone(KST)
    e = end.astimezone(KST)
    now = datetime.now(KST)
    api_floor = (now - timedelta(days=3)).replace(hour=0, minute=0, second=0, microsecond=0)
    if s < api_floor:
        print(
            f"단기예보 API는 최근 3일만 제공합니다. 시작 시각을 {api_floor.isoformat()} 로 맞춥니다.",
            file=sys.stderr,
        )
        s = api_floor

    store: dict[tuple[str, str], tuple[int, dict[str, str]]] = {}
    skipped_calls = 0

    day = s.date()
    end_day = e.date()
    while day <= end_day:
        base_date = day.strftime("%Y%m%d")
        for base_time in VILAGE_ISSUE_TIMES:
            try:
                iss_dt = datetime.strptime(base_date + base_time, "%Y%m%d%H%M").replace(tzinfo=KST)
            except ValueError:
                continue
            if iss_dt > now:
                continue
            page = 1
            while True:
                qs: dict[str, str] = {
                    "serviceKey": key,
                    "pageNo": str(page),
                    "numOfRows": "1000",
                    "dataType": "JSON",
                    "base_date": base_date,
                    "base_time": base_time,
                    "nx": str(nx),
                    "ny": str(ny),
                }
                url = VILAGE_URL + "?" + urllib.parse.urlencode(qs)
                data = http_get_json(url, sleep_s)
                hdr = data.get("response", {}).get("header", {})
                rc = str(hdr.get("resultCode", "")).strip()
                if rc != "00":
                    skipped_calls += 1
                    break
                items = parse_kma_items(data)
                if not items:
                    break
                iss = int(base_date + base_time)
                by_slot: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
                for it in items:
                    fd = str(it.get("fcstDate") or "").strip()
                    ft = str(it.get("fcstTime") or "").strip().zfill(4)
                    cat = (it.get("category") or "").strip()
                    val = it.get("fcstValue")
                    if not fd or not ft or not cat or val is None:
                        continue
                    by_slot[(fd, ft)][cat] = str(val)
                for key_ft, cats in by_slot.items():
                    try:
                        fdt = fcst_datetime_kst(key_ft[0], key_ft[1])
                    except ValueError:
                        continue
                    if fdt < s or fdt > e:
                        continue
                    prev = store.get(key_ft)
                    if prev is None or iss > prev[0]:
                        store[key_ft] = (iss, dict(cats))
                n = len(items)
                if n < int(qs["numOfRows"]):
                    break
                page += 1
        day += timedelta(days=1)

    written = 0
    for key_ft in sorted(store.keys(), key=lambda k: fcst_datetime_kst(k[0], k[1])):
        _iss, cats = store[key_ft]
        fdt = fcst_datetime_kst(key_ft[0], key_ft[1])
        ts_ns = int(fdt.timestamp() * 1e9)
        temp = num_or_none(cats.get("TMP"))
        reh = num_or_none(cats.get("REH"))
        vec = num_or_none(cats.get("VEC"))
        wsd = num_or_none(cats.get("WSD"))
        pty = int_or_none(cats.get("PTY"))
        line = line_protocol_tele_kma(ts_ns, nx, ny, temp, reh, vec, wsd, pty)
        if not line:
            continue
        if dry_run:
            print(line[:140] + ("..." if len(line) > 140 else ""))
        else:
            influx_write(env, line)
        written += 1

    return written, skipped_calls


def main() -> int:
    ap = argparse.ArgumentParser(description="KMA/ASOS → Influx tele 백필")
    ap.add_argument("--start", default="2026-05-01", help="KST 기준 시작일 YYYY-MM-DD")
    ap.add_argument("--end", default="", help="KST 기준 종료(미입력 시 지금)")
    ap.add_argument(
        "--mode",
        choices=("vilage", "asos", "ncst"),
        default="vilage",
        help="vilage=단기예보(최근3일), asos=ASOS시간(별도신청), ncst=초단기실황(최근1일)",
    )
    ap.add_argument("--stn-ids", default="", help="ASOS 관측소 번호(쉼표 구분). 미입력 시 env CRONUSFARM_KMA_ASOS_STN")
    ap.add_argument("--step-hours", type=int, default=1, help="ncst 모드 시간 간격")
    ap.add_argument("--sleep", type=float, default=0.25, help="요청 간 대기(초)")
    ap.add_argument("--dry-run", action="store_true", help="Influx 쓰기 없이 라인 샘플만")
    args = ap.parse_args()

    env = merge_env()

    start = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=KST)
    if args.end.strip():
        end = datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=KST) + timedelta(days=1) - timedelta(seconds=1)
    else:
        end = datetime.now(KST)

    if not env.get("CRONUSFARM_INFLUX_TOKEN"):
        raise SystemExit("CRONUSFARM_INFLUX_TOKEN 없음 (drop-in 또는 환경변수)")

    if args.mode == "vilage":
        w, s = backfill_vilage(env, start, end, args.sleep, args.dry_run)
        print(f"VilageFcst 백필: 시계열 {w} 건, API 스킵 호출 {s} 회 (dry_run={args.dry_run})")
    elif args.mode == "asos":
        stn = (args.stn_ids or env.get("CRONUSFARM_KMA_ASOS_STN", "")).strip()
        if not stn:
            raise SystemExit(
                "ASOS 관측소 번호가 필요합니다. 예: --stn-ids 119 또는 "
                "drop-in에 Environment=CRONUSFARM_KMA_ASOS_STN=119"
            )
        w, s = backfill_asos(env, stn, start, end, args.sleep, args.dry_run)
        print(f"ASOS 백필 완료: 기록 {w} 건, 스킵 {s} 건 (dry_run={args.dry_run})")
    else:
        w, s = backfill_ncst(env, start, end, args.step_hours, args.sleep, args.dry_run)
        print(f"NCST 백필 완료: 기록 {w} 건, 스킵 {s} 건 (dry_run={args.dry_run})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
