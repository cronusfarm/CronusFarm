# -*- coding: utf-8 -*-
"""Water Quality (24h) — 계단식(stepped) 제거, EC 포함 유선형(monotone) 곡선."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_FLOW_DIR = Path(__file__).resolve().parent

_spec = importlib.util.spec_from_file_location(
    "patch_monitor_ui_requests", _FLOW_DIR / "patch_monitor_ui_requests.py"
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
PHW_FMT = _mod.PHW_CHART_FMT

FLOW_FILES = [
    ROOT / "nodered" / "flows_cronusfarm_dashboard.json",
    ROOT / "nodered" / "flows_cronusfarm_mqtt.json",
    ROOT / "nodered" / "merged-deploy.json",
    ROOT / "nodered" / "CronusFarm_NodeRED_flow.json",
]

CHART_ID = "ui_tpl_phw_water_24h"


def patch_file(path: Path) -> list[str]:
    if not path.is_file():
        return []
    flows = json.loads(path.read_text(encoding="utf-8-sig"))
    changed: list[str] = []
    for n in flows:
        if not isinstance(n, dict) or n.get("id") != CHART_ID:
            continue
        old = n.get("format") or ""
        if old != PHW_FMT:
            n["format"] = PHW_FMT
            changed.append(path.name)
        break
    if changed:
        path.write_text(
            json.dumps(flows, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    return changed


def main() -> int:
    all_c: list[str] = []
    for fp in FLOW_FILES:
        all_c.extend(patch_file(fp))
    if not all_c:
        print("WARN patch_phw_water_smooth: no changes")
        return 1
    print("OK patch_phw_water_smooth:", ", ".join(sorted(set(all_c))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
