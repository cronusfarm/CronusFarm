#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DB schedule_rule vs scripts/cronusfarm_schedule_defaults.py 비교·출력."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from cronusfarm_schedule_defaults import DEFAULT_SCHEDULE_RULES, DEFAULT_DEVICE_ID  # noqa: E402


def min_to_hm(m: int) -> str:
    h, mm = divmod(int(m), 60)
    return f"{h:02d}:{mm:02d}"


def fmt_rule(r: dict) -> str:
    rk = r.get("rule_kind", "window")
    dow = int(r.get("dow_mask", 127))
    on_m = int(r.get("on_min", 0))
    off_m = int(r.get("off_min", 0))
    en = int(r.get("enabled", 1))
    slot = int(r.get("slot_index", 0))
    if rk == "cycle":
        on_s = int(r.get("on_sec", 0))
        off_s = int(r.get("off_sec", 0))
        win = ""
        if on_m != 0 or off_m != 0:
            win = f" [{min_to_hm(on_m)}~{min_to_hm(off_m)}]"
        return (
            f"slot{slot} cycle ON {on_s}s/OFF {off_s}s{win} "
            f"dow={dow} en={en}"
        )
    return (
        f"slot{slot} window {min_to_hm(on_m)}~{min_to_hm(off_m)} "
        f"dow={dow} en={en}"
    )


def norm_rules(rules: list[dict]) -> list[tuple]:
    out = []
    for r in rules:
        out.append(
            (
                str(r.get("rule_kind", "window")),
                int(r.get("dow_mask", 127)),
                int(r.get("slot_index", 0)),
                int(r.get("on_min", 0)),
                int(r.get("off_min", 0)),
                int(r.get("enabled", 1)),
                r.get("on_sec"),
                r.get("off_sec"),
            )
        )
    return sorted(out)


def load_db(path: Path, device_id: str) -> dict[str, list[dict]]:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """SELECT channel_key, rule_kind, dow_mask, slot_index, on_min, off_min,
                  enabled, on_sec, off_sec, updated_at
           FROM schedule_rule WHERE device_id=? ORDER BY channel_key, slot_index, id""",
        (device_id,),
    )
    by_ch: dict[str, list[dict]] = {}
    for row in cur.fetchall():
        ch = row["channel_key"]
        by_ch.setdefault(ch, []).append(
            {
                "rule_kind": row["rule_kind"],
                "dow_mask": row["dow_mask"],
                "slot_index": row["slot_index"],
                "on_min": row["on_min"],
                "off_min": row["off_min"],
                "enabled": row["enabled"],
                "on_sec": row["on_sec"],
                "off_sec": row["off_sec"],
                "updated_at": row["updated_at"],
            }
        )
    conn.close()
    return by_ch


def main() -> None:
    db_path = Path(
        sys.argv[1] if len(sys.argv) > 1 else "/home/dooly/.node-red/cronusfarm.sqlite"
    )
    device_id = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_DEVICE_ID
    if not db_path.is_file():
        print("ERROR: DB 없음", db_path, file=sys.stderr)
        sys.exit(1)

    db = load_db(db_path, device_id)
    hard = DEFAULT_SCHEDULE_RULES
    all_ch = sorted(set(hard.keys()) | set(db.keys()))

    print(f"=== DB 스케줄 ({device_id}) ===\n")
    for ch in all_ch:
        rules = db.get(ch, [])
        if not rules:
            print(f"[{ch}] (DB 없음)")
            continue
        print(f"[{ch}]")
        for r in rules:
            print("  ", fmt_rule(r), f"updated={r.get('updated_at','')}")
        print()

    print("\n=== 하드코딩 기본값 (cronusfarm_schedule_defaults.py) ===\n")
    for ch in all_ch:
        rules = hard.get(ch, [])
        if not rules:
            continue
        print(f"[{ch}]")
        for r in rules:
            print("  ", fmt_rule(r))
        print()

    print("\n=== 차이 (DB vs 하드코딩) ===\n")
    diff_any = False
    for ch in all_ch:
        d = norm_rules(db.get(ch, []))
        h = norm_rules(hard.get(ch, []))
        if d == h:
            continue
        diff_any = True
        print(f"** {ch} **")
        if not d:
            print("  DB: (규칙 없음)")
        else:
            for r in db.get(ch, []):
                print("  DB:", fmt_rule(r))
        if not h:
            print("  HC: (규칙 없음)")
        else:
            for r in hard.get(ch, []):
                print("  HC:", fmt_rule(r))
        print()
    if not diff_any:
        print("(채널별 규칙 내용 동일)")


if __name__ == "__main__":
    main()
