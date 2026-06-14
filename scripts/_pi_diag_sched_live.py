#!/usr/bin/env python3
"""현재 KST 기준 스케줄 기대값 vs tele S/A/G."""
import sqlite3
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

DB = "/home/dooly/.node-red/cronusfarm.sqlite"
DEV = "cronusfarm-01"
KST = ZoneInfo("Asia/Seoul")

ALL_CH = [
    "led_a1", "led_a2", "led_b1", "pump_a1", "pump_a2", "pump_b1", "pump_b2",
    "fan_a1", "fan_a2", "fan_b1", "fan_b2", "pump_c1", "pump_c2", "pump_d1", "pump_d2", "led_b2",
]


def parse_kv(part: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for tok in (part or "").split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            out[k] = v
    return out


def in_window(now_min: int, on_min: int, off_min: int) -> bool:
    if on_min == off_min:
        return False
    if on_min < off_min:
        return on_min <= now_min < off_min
    return now_min >= on_min or now_min < off_min


def cycle_want(sec_day: int, on_sec: int, off_sec: int) -> bool:
    per = on_sec + off_sec
    if per <= 0:
        return False
    return (sec_day % per) < on_sec


def dow_mask_today(dt: datetime) -> int:
    # Arduino cfRtcDowToUiMask: Sun=1 Mon=2 ... Sat=64
    return 1 << ((dt.weekday() + 1) % 7)


def sch_want_channel(cur, ch: str, dt: datetime) -> bool | None:
    now_min = dt.hour * 60 + dt.minute
    sec_day = dt.hour * 3600 + dt.minute * 60 + dt.second
    dow = dow_mask_today(dt)
    cur.execute(
        """SELECT rule_kind, dow_mask, on_min, off_min, on_sec, off_sec, enabled
           FROM schedule_rule
           WHERE device_id=? AND channel_key=? AND enabled=1
           ORDER BY slot_index, id""",
        (DEV, ch),
    )
    rows = cur.fetchall()
    if not rows:
        return None
    for rk, dm, on_m, off_m, on_s, off_s, en in rows:
        if not en or not (int(dm) & dow):
            continue
        kind = (rk or "window").strip().lower()
        if kind == "window":
            if in_window(now_min, int(on_m), int(off_m)):
                return True
        else:
            if int(on_m) or int(off_m):
                if not in_window(now_min, int(on_m), int(off_m)):
                    continue
            if cycle_want(sec_day, int(on_s or 0), int(off_s or 0)):
                return True
    return False


def main() -> None:
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(
        "SELECT raw FROM tele_sample WHERE device_id=? ORDER BY ts_ms DESC LIMIT 1",
        (DEV,),
    )
    row = cur.fetchone()
    raw = (row[0] if row else "") or ""
    kv_s = kv_a = {}
    g_part = ""
    for seg in raw.split("|"):
        seg = seg.strip()
        if seg.startswith("S:"):
            kv_s = parse_kv(seg[2:])
        elif seg.startswith("A:"):
            kv_a = parse_kv(seg[2:])
        elif seg.startswith("G:"):
            g_part = seg[2:].strip()

    now = datetime.now(KST)
    print(f"now {now.strftime('%Y-%m-%d %H:%M:%S KST')} min={now.hour*60+now.minute}")
    print(f"tele G: {g_part or 'ok'}")
    print(f"\n{'channel':14} {'auto':5} {'tele':5} {'sch':5} {'match':5}")
    print("-" * 44)
    mism = 0
    for ch in ALL_CH:
        auto = kv_a.get(ch, "?")
        tele = kv_s.get(ch, "?")
        want = sch_want_channel(cur, ch, now)
        if want is None:
            sch = "n/a"
            ok = "?"
        else:
            sch = "ON" if want else "OFF"
            t_on = tele == "1"
            ok = "OK" if (want == t_on) else "!!"
            if ok == "!!":
                mism += 1
        print(f"{ch:14} {auto:5} {('ON' if tele=='1' else 'OFF' if tele=='0' else tele):5} {sch:5} {ok:5}")
    print(f"\nmismatch={mism}")
    if mism:
        sys.exit(1)


if __name__ == "__main__":
    main()
