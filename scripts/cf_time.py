#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CronusFarm 운영 시각 — Pi(Asia/Seoul) 단일 기준.

원칙:
- Pi OS 타임존을 Asia/Seoul 로 맞춘 뒤(scripts/pi-set-timezone-seoul.sh) 서버는 로컬 시각=KST.
- DB·MQTT 타임스탬프는 UTC epoch ms(ts_ms) 저장.
- 브라우저는 /api/time/now 로 Pi 시각을 주기 동기(skew)만 적용.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

CRONUSFARM_TZ = "Asia/Seoul"
_KST = ZoneInfo(CRONUSFARM_TZ)


def now_kst() -> datetime:
    return datetime.now(_KST)


def now_ms() -> int:
    return int(now_kst().timestamp() * 1000)


def kst_calendar_day_window_ms(now_ms: int | None = None) -> tuple[int, int, int]:
    """오늘 0:00~내일 0:00 KST (epoch ms). 반환: (anchor, day_end, ref)."""
    ref = int(now_ms if now_ms is not None else time.time() * 1000)
    dt = datetime.fromtimestamp(ref / 1000, tz=_KST)
    start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000), ref


def format_local(ms: int | None = None) -> str:
    """Pi KST 표시 문자열 YYYY-MM-DD HH:MM:SS"""
    ref = int(ms if ms is not None else now_ms())
    return datetime.fromtimestamp(ref / 1000, tz=_KST).strftime("%Y-%m-%d %H:%M:%S")


def query_time_now() -> dict[str, object]:
    """브라우저·NR 시계 동기용(가벼운 JSON)."""
    ts = now_ms()
    anchor, day_end, _ = kst_calendar_day_window_ms(ts)
    return {
        "pi_ts_ms": ts,
        "pi_local_display": format_local(ts),
        "pi_tz": CRONUSFARM_TZ,
        "day_anchor_ms": anchor,
        "day_end_ms": day_end,
    }
