# -*- coding: utf-8 -*-
"""모니터 타임라인: KST 0시 anchor + 48h 조회(어제 09시~ 포함)."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
MON_PATCH = ROOT / "scripts" / "patch_dashboard_monitor_ai_timeline_bedbox.py"

OLD_MAP = re.compile(
    r"function mapTime\(j\) \{.*?return \{ tStart: tEnd - hrs \* 3600 \* 1000, tEnd: tEnd \};",
    re.DOTALL,
)

NEW_MAP = r"""function mapTime(j) {
    const h = Number(j.hours);
    const hrs = (isFinite(h) && h >= 1 && h <= 168) ? h : 24;
    const tEnd = (j.window_end_ms != null && isFinite(Number(j.window_end_ms))) ? Number(j.window_end_ms) : Date.now();
    let tStart;
    if (hrs === 24 && j.anchor_ts_ms != null && isFinite(Number(j.anchor_ts_ms))) {
      tStart = Number(j.anchor_ts_ms);
    } else {
      tStart = tEnd - hrs * 3600 * 1000;
    }
    return { tStart: tStart, tEnd: tEnd };
  }"""


def patch_format(fmt: str) -> tuple[str, bool]:
    orig = fmt
    fmt = OLD_MAP.sub(NEW_MAP, fmt, count=1)
    fmt = fmt.replace("&hours=24'", "&hours=48'")
    fmt = fmt.replace("24h ON/OFF", "48h ON/OFF")
    return fmt, fmt != orig


def main() -> None:
    n = 0
    for path in (DASH,):
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        for node in data:
            nid = str(node.get("id", ""))
            if not nid.startswith("ui_tpl_hist_stack_"):
                continue
            fmt = node.get("format") or ""
            new_fmt, chg = patch_format(fmt)
            if chg:
                node["format"] = new_fmt
                n += 1
        if n:
            path.write_text(
                json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            print("OK", path.name, n)

    # bedbox generator template source
    txt = MON_PATCH.read_text(encoding="utf-8")
    if "function mapTime(j)" in txt and NEW_MAP not in txt:
        txt2 = OLD_MAP.sub(NEW_MAP, txt, count=1)
        txt2 = txt2.replace("&hours=24'", "&hours=48'")
        txt2 = txt2.replace("24h ON/OFF", "48h ON/OFF")
        MON_PATCH.write_text(txt2, encoding="utf-8")
        print("OK patch_dashboard_monitor_ai_timeline_bedbox.py template")


if __name__ == "__main__":
    main()
