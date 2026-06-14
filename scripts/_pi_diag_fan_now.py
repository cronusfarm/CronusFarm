#!/usr/bin/env python3
"""Fan A1/A2/B1/B2 — 스케줄 기대 vs tele·AUTO·수동 홀드."""
import sqlite3
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

DB = "/home/dooly/.node-red/cronusfarm.sqlite"
DEV = "cronusfarm-01"
FANS = ("fan_a1", "fan_a2", "fan_b1", "fan_b2")
KST = ZoneInfo("Asia/Seoul")


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


def main() -> None:
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(
        "SELECT raw, ts_ms FROM tele_sample WHERE device_id=? ORDER BY ts_ms DESC LIMIT 1",
        (DEV,),
    )
    row = cur.fetchone()
    raw = (row[0] if row else "") or ""
    tele_ts = row[1] if row else None
    kv_s = kv_a = {}
    g = ""
    for seg in raw.split("|"):
        seg = seg.strip()
        if seg.startswith("S:"):
            kv_s = parse_kv(seg[2:])
        elif seg.startswith("A:"):
            kv_a = parse_kv(seg[2:])
        elif seg.startswith("G:"):
            g = seg[2:].strip()
        elif seg.startswith("R:"):
            rtc = seg[2:].strip()

    now = datetime.now(KST)
    nm = now.hour * 60 + now.minute
    print(f"now_kst={now.strftime('%Y-%m-%d %H:%M:%S')} minute={nm}")
    if tele_ts:
        age = int((now.timestamp() * 1000 - tele_ts) / 1000)
        print(f"tele_age_sec={age}")
    print(f"tele_G={g or 'ok'}")
    if "R:" in raw:
        for seg in raw.split("|"):
            if seg.strip().startswith("R:"):
                print(f"arduino_rtc={seg.strip()[2:]}")
                break

    print("\nchannel       auto  tele  sched   hold?   rules")
    print("-" * 72)
    for ch in FANS:
        auto = kv_a.get(ch, "?")
        tele = kv_s.get(ch, "?")
        cur.execute(
            """SELECT rule_kind, on_min, off_min, enabled FROM schedule_rule
               WHERE device_id=? AND channel_key=? ORDER BY slot_index""",
            (DEV, ch),
        )
        rules = cur.fetchall()
        want = False
        for rk, on_m, off_m, en in rules:
            if en and (rk or "window") == "window":
                if in_window(nm, int(on_m), int(off_m)):
                    want = True
        sched = "ON" if want else "OFF"
        cur.execute(
            """SELECT expires_ms FROM channel_manual_hold
               WHERE device_id=? AND channel_key=? AND expires_ms > ?""",
            (DEV, ch, int(now.timestamp() * 1000)),
        )
        hold = cur.fetchone()
        hold_txt = "YES" if hold else "no"
        match = "OK" if (tele == "1") == want and auto == "1" else "MISMATCH"
        print(
            f"{ch:12}  {auto:4}  {tele:4}  {sched:5}  {hold_txt:5}  {match}  {rules}"
        )

    cur.execute(
        """SELECT channel_key, source, new_state, ts_ms FROM manual_switch_event
           WHERE device_id=? AND channel_key LIKE 'fan_%'
           ORDER BY ts_ms DESC LIMIT 8""",
        (DEV,),
    )
    ev = cur.fetchall()
    if ev:
        print("\nrecent fan manual_switch_event:")
        for r in ev:
            print(" ", r)


if __name__ == "__main__":
    main()
