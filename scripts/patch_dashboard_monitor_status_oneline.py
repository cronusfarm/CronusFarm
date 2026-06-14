# -*- coding: utf-8 -*-
"""모니터 Arduino 상태 4행: 펌프 가드와 동일 한 줄 높이."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import re

from _r4_status_oneline import LABELS, ORDERS, ROW_CSS_MARK, TELE_GUARD_FMT, formats  # noqa: E402

SRV_INLAY_CSS_MARK = "/* R4 MQTT·Mosquitto:"
SRV_INLAY_CSS = """/* R4 MQTT·Mosquitto: retain 줄과 같은 안쪽 박스(cf-mqtt-unified-bar 계열) */
.nr-dashboard-theme .nr-dashboard-group .nr-dashboard-template:has(.cf-srv-inlay){
  overflow: hidden !important;
  overflow-y: hidden !important;
}
.cf-srv-inlay{
  margin: 0;
  padding: 0;
  width: 100%;
  box-sizing: border-box;
  overflow: hidden;
}
.cf-srv-inlay-bar{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 6px 10px;
  background: rgba(79,140,255,.08);
  border: 1px solid rgba(79,140,255,.22);
  border-radius: 10px;
  box-sizing: border-box;
  overflow: hidden;
  min-height: 0;
}
.cf-srv-inlay-text{
  min-width: 0;
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.cf-srv-inlay-title{
  font-size: 12px;
  font-weight: 800;
  color: var(--cf-text,#e6edf7);
  line-height: 1.15;
}
.cf-srv-inlay-sub{
  font-size: 9px;
  line-height: 1.15;
  color: var(--cf-muted,#9db0cc);
  opacity: .92;
}
.cf-srv-inlay-status{
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  white-space: nowrap;
}
.cf-srv-inlay-st{
  font-size: 12px;
  font-weight: 800;
  color: var(--cf-text,#e6edf7);
  font-variant-numeric: tabular-nums;
}
.cf-srv-inlay-text--compact{
  gap: 0;
  justify-content: center;
}
.cf-route-sum .cf-srv-inlay-bar{
  background: rgba(255,255,255,.06);
  border-color: rgba(255,255,255,.14);
}
.cf-route-ok .cf-srv-inlay-bar{
  background: rgba(46,125,50,.14);
  border-color: rgba(102,187,106,.35);
}
.cf-route-warn .cf-srv-inlay-bar{
  background: rgba(245,124,0,.12);
  border-color: rgba(255,183,77,.38);
}
.cf-route-bad .cf-srv-inlay-bar{
  background: rgba(198,40,40,.14);
  border-color: rgba(239,83,80,.38);
}
.cf-dot-warn{
  background: #ffb74d !important;
  box-shadow: 0 0 8px rgba(255,183,77,.55);
}
"""

CONN_ONE_LINE_CSS = """.cf-srv-inlay-title--one{
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cf-dot-warn{background:#ffb300 !important;box-shadow:0 0 6px rgba(255,179,0,.55);}
.cf-route-sum .cf-srv-inlay-bar{border-width:1px;}
.cf-route-ok .cf-srv-inlay-bar{background:rgba(46,125,50,.12);border-color:rgba(102,187,106,.35);}
.cf-route-warn .cf-srv-inlay-bar{background:rgba(255,179,0,.10);border-color:rgba(255,179,0,.35);}
.cf-route-bad .cf-srv-inlay-bar{background:rgba(198,40,40,.12);border-color:rgba(239,83,80,.35);}
"""


def _strip_legacy_r4_css(fmt: str) -> str:
    """구 cf-r4-status 전역 블록 제거 — 각 행은 펌프가드와 동일 인라인 CSS 사용."""
    if ROW_CSS_MARK not in fmt:
        return fmt
    return re.sub(
        r"/\* cf-r4-status \*/.*?(?=/\* cf-r4-status \*/|</style>)",
        "",
        fmt,
        count=1,
        flags=re.DOTALL,
    )

FLOW_FILES = [
    ROOT / "nodered" / "flows_cronusfarm_dashboard.json",
    ROOT / "nodered" / "flows_cronusfarm_mqtt.json",
    ROOT / "nodered" / "merged-deploy.json",
    ROOT / "nodered" / "CronusFarm_NodeRED_flow.json",
]

FN_CALC = "fn_calc_online"
CSS_NODE = "ui_tpl_css_cronus"
TILES_CSS = "ui_tpl_css_tiles_v1"
FMT_MAP = formats()


def patch_file(path: Path) -> list[str]:
    if not path.is_file():
        return []
    flows = json.loads(path.read_text(encoding="utf-8-sig"))
    by = {n["id"]: n for n in flows if isinstance(n, dict) and n.get("id")}
    changed: list[str] = []

    css = by.get(CSS_NODE)
    if css:
        fmt = _strip_legacy_r4_css(css.get("format") or "")
        if fmt != (css.get("format") or ""):
            css["format"] = fmt
            changed.append(f"{CSS_NODE}:strip-r4")

    tiles = by.get(TILES_CSS)
    if tiles:
        tfmt = tiles.get("format") or ""
        if SRV_INLAY_CSS_MARK not in tfmt and "cf-srv-inlay-bar" not in tfmt:
            if "</style>" in tfmt:
                tfmt = tfmt.replace("</style>", SRV_INLAY_CSS + "</style>", 1)
            else:
                tfmt += f"<style>{SRV_INLAY_CSS}</style>"
        if "cf-srv-inlay-title--one" not in tfmt and "</style>" in tfmt:
            tfmt = tfmt.replace("</style>", CONN_ONE_LINE_CSS + "</style>", 1)
        if tfmt != (tiles.get("format") or ""):
            tiles["format"] = tfmt
            changed.append(TILES_CSS)

    calc = by.get(FN_CALC)
    if calc:
        want_wires = [
            ["ui_tpl_farm_route_summary"],
            ["ui_tpl_conn_line"],
            ["ui_tpl_r4_usb_line"],
            ["ui_tpl_status_line"],
            ["ui_tpl_r3_panel_line"],
        ]
        if calc.get("outputs") != 5:
            calc["outputs"] = 5
            changed.append(f"{FN_CALC}:outputs")
        if calc.get("wires") != want_wires:
            calc["wires"] = want_wires
            changed.append(f"{FN_CALC}:wires")

    guard = by.get("ui_tpl_tele_guard")
    if guard:
        if guard.get("format") != TELE_GUARD_FMT:
            guard["format"] = TELE_GUARD_FMT
            changed.append("ui_tpl_tele_guard")
        if guard.get("name") != "펌프 가드":
            guard["name"] = "펌프 가드"
            changed.append("ui_tpl_tele_guard:name")
        if guard.get("order") != 7:
            guard["order"] = 7
            changed.append("ui_tpl_tele_guard:order")
        if guard.get("height") != 1:
            guard["height"] = 1
        if guard.get("group") != "ui_grp_arduino":
            guard["group"] = "ui_grp_arduino"

    for nid, fmt in FMT_MAP.items():
        n = by.get(nid)
        if not n:
            continue
        if n.get("format") != fmt:
            n["format"] = fmt
            changed.append(nid)
        if n.get("height") != 1:
            n["height"] = 1
            changed.append(f"{nid}:h")
        if n.get("width") != "12":
            n["width"] = "12"
        if n.get("group") != "ui_grp_arduino":
            n["group"] = "ui_grp_arduino"
        if ORDERS.get(nid) and n.get("order") != ORDERS[nid]:
            n["order"] = ORDERS[nid]
            changed.append(f"{nid}:order")
        want_name = LABELS.get(nid)
        if want_name and n.get("name") != want_name:
            n["name"] = want_name
            changed.append(f"{nid}:name")
        if n.get("storeOutMessages") is not False:
            n["storeOutMessages"] = False
        if n.get("fwdInMessages") is not False:
            n["fwdInMessages"] = False

    if changed:
        path.write_text(
            json.dumps(flows, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    return [f"{path.name}:{c}" for c in changed]


def main() -> int:
    all_c: list[str] = []
    for fp in FLOW_FILES:
        all_c.extend(patch_file(fp))
    if not all_c:
        print("WARN patch_dashboard_monitor_status_oneline: no changes")
        return 1
    print("OK patch_dashboard_monitor_status_oneline:", ", ".join(sorted(set(all_c))[:20]), "...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
