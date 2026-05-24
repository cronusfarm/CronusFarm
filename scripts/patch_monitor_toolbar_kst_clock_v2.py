#!/usr/bin/env python3
"""모니터 툴바 시계 V2: __cfMonitorToolbarClockV2 + Pi API 보정 + KST 접미사."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from patch_dashboard_monitor_ai_timeline_bedbox import MONITOR_CLOCK_BOOT  # noqa: E402

PATHS = [
    ROOT / "nodered" / "flows_cronusfarm_dashboard.json",
    ROOT / "nodered" / "flows_pi_editor_latest.json",
    ROOT / "nodered" / "merged-deploy.json",
]

RE_CLOCK_SCRIPT = re.compile(
    r"<script\s+type=[\"']text/javascript[\"']>\s*\(function\(\)\{\s*"
    r"if\(window\.__cfMonitorToolbarClock",
    re.IGNORECASE,
)


def patch_ai_stream(fmt: str) -> tuple[str, bool]:
    if "cf-monitor-tab-clock" not in fmt or "cf-ai-cam-outer" not in fmt:
        return fmt, False
    if "__cfMonitorToolbarClockV2" in fmt and " KST" in fmt and "syncServer" in fmt:
        return fmt, False
    m = RE_CLOCK_SCRIPT.search(fmt)
    if not m:
        return fmt, False
    end = fmt.find("</script>", m.start())
    if end < 0:
        return fmt, False
    end += len("</script>")
    return fmt[: m.start()] + MONITOR_CLOCK_BOOT.strip() + "\n" + fmt[end:], True


def main() -> int:
    n = 0
    for path in PATHS:
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for node in data:
            if node.get("id") != "nr_node_ui_ai_stream":
                continue
            fmt = node.get("format") or ""
            new_fmt, did = patch_ai_stream(fmt)
            if did:
                node["format"] = new_fmt
                changed = True
                n += 1
                print(f"patched {path.name} {node.get('id')}")
        if changed:
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    print(f"OK ({n} nodes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
