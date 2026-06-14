# -*- coding: utf-8 -*-
"""farm-ui scheduleDefaultsDisplay.js → patch_dashboard 상수 동기화."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "farm-ui" / "src" / "constants" / "scheduleDefaultsDisplay.js"
PATCH = ROOT / "scripts" / "patch_dashboard_monitor_ai_timeline_bedbox.py"


def main() -> None:
    js = JS.read_text(encoding="utf-8")
    m = re.search(
        r"export const SCHEDULE_DEFAULTS_BEDS = (\[[\s\S]*?\])\s*$",
        js,
        re.MULTILINE,
    )
    if not m:
        raise SystemExit("SCHEDULE_DEFAULTS_BEDS not found in JS")
    beds_js = m.group(1)
    # JS → Python dict literal (label/detail quotes only)
    py_beds = (
        beds_js.replace("label:", '"label":')
        .replace("rule:", '"rule":')
        .replace("detail:", '"detail":')
        .replace("bed:", '"bed":')
        .replace("rows:", '"rows":')
        .replace("'", '"')
    )
    patch = PATCH.read_text(encoding="utf-8")
    pat = r"# farm-ui scheduleDefaultsDisplay\.js 와 동일[\s\S]*?^\]\n\n# 실제 동작"
    repl = (
        "# farm-ui scheduleDefaultsDisplay.js 와 동일 (builtin·DB 시드)\n"
        f"SCHEDULE_DEFAULTS_BEDS = {py_beds}\n\n\n# 실제 동작"
    )
    new_patch, n = re.subn(pat, repl, patch, count=1, flags=re.MULTILINE)
    if n != 1:
        raise SystemExit("patch_dashboard SCHEDULE_DEFAULTS_BEDS block not found")
    PATCH.write_text(new_patch, encoding="utf-8")
    print("updated", PATCH)


if __name__ == "__main__":
    main()
