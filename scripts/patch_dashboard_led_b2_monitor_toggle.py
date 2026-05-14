# -*- coding: utf-8 -*-
"""모니터(ui_grp_b): LED B2 토글 타일 + tele/cmd 라우팅(led_b2, auto_led_b2)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

TOGGLE_FMT = (
    '<div class="cf-tile" ng-click="send({topic:\'led_b2\', payload:(msg.payload==1?0:1)})">'
    '<div class="cf-tile-left"><div class="cf-ic" aria-hidden="true">'
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="#FFD54F" d="M9 21c0-3 2-5 3-6s3-3 3-6a6 6 0 0 0-12 0c0 3 2 5 3 6s3 3 3 6z"/></svg></div>'
    '<div class="cf-tile-txt"><div class="cf-tile-name">LED B2</div>'
    '<div class="cf-tile-sub">(R4-D13) · 탭하여 토글(수동)</div></div></div>'
    '<div class="cf-tile-right"><div class="cf-dot" ng-class="msg.payload==1 ? \'cf-dot-on\' : \'cf-dot-off\'"></div>'
    '<div class="cf-pill" ng-class="msg.payload==1 ? \'cf-on\' : \'cf-off\'">'
    "{{msg.payload==1 ? 'ON' : 'OFF'}}</div></div></div>"
)


def _patch_parse_tele(func: str) -> str:
    if "'led_b2'" in func:
        return func
    old = "['led_a1','led_a2','pump_a1','pump_a2','led_b1','pump_b1','pump_b2','fan_a1','fan_a2','fan_b1','fan_b2','pump_c1','pump_c2','pump_d1','pump_d2']"
    new = "['led_a1','led_a2','pump_a1','pump_a2','led_b1','led_b2','pump_b1','pump_b2','fan_a1','fan_a2','fan_b1','fan_b2','pump_c1','pump_c2','pump_d1','pump_d2']"
    if old not in func:
        raise SystemExit("fn_parse_tele_v2: chKeys 배열 앵커 없음")
    return func.replace(old, new, 1)


def _patch_cmd_merge(func: str) -> str:
    if "'auto_led_b2'" in func:
        return func
    old = (
        "  'led_a1','led_a2','pump_a1','pump_a2','led_b1','pump_b1','pump_b2',\n"
        "  'auto_led_a1','auto_led_a2','auto_pump_a1','auto_pump_a2','auto_led_b1','auto_pump_b1','auto_pump_b2',\n"
    )
    new = (
        "  'led_a1','led_a2','pump_a1','pump_a2','led_b1','led_b2','pump_b1','pump_b2',\n"
        "  'auto_led_a1','auto_led_a2','auto_pump_a1','auto_pump_a2','auto_led_b1','auto_led_b2','auto_pump_b1','auto_pump_b2',\n"
    )
    if old not in func:
        raise SystemExit("fn_cmd_merge_v2: keys 배열 앵커 없음")
    return func.replace(old, new, 1)


def main() -> None:
    d = json.loads(DASH.read_text(encoding="utf-8-sig"))
    by_id = {n.get("id"): n for n in d if isinstance(n, dict)}

    n = by_id.get("ui_tpl_mon_b_resv1") or by_id.get("ui_tpl_toggle_led_b2")
    if not n:
        raise SystemExit("ui_tpl_mon_b_resv1 / ui_tpl_toggle_led_b2 없음")
    n["id"] = "ui_tpl_toggle_led_b2"
    n["name"] = "LED B2 토글"
    n["format"] = TOGGLE_FMT
    n["wires"] = [["fn_force_manual_and_set"]]
    n["storeOutMessages"] = False
    n["fwdInMessages"] = True
    n["resendOnRefresh"] = True
    n["templateScope"] = "local"

    pt = by_id.get("fn_parse_tele_v2")
    if not pt:
        raise SystemExit("fn_parse_tele_v2 없음")
    pt["func"] = _patch_parse_tele(pt.get("func") or "")

    cm = by_id.get("fn_cmd_merge_v2")
    if not cm:
        raise SystemExit("fn_cmd_merge_v2 없음")
    cm["func"] = _patch_cmd_merge(cm.get("func") or "")

    sw = by_id.get("sw_route_state")
    if not sw:
        raise SystemExit("sw_route_state 없음")
    rules = sw.get("rules") or []
    wires = sw.get("wires") or []
    if any(r.get("v") == "led_b2" for r in rules):
        pass
    else:
        idx = next((i for i, r in enumerate(rules) if r.get("v") == "led_b1"), None)
        if idx is None:
            raise SystemExit("sw_route_state: led_b1 규칙 없음")
        insert_at = idx + 1
        rules.insert(insert_at, {"t": "eq", "v": "led_b2", "vt": "str"})
        wires.insert(insert_at, ["ui_tpl_toggle_led_b2"])
        sw["rules"] = rules
        sw["wires"] = wires
        sw["outputs"] = len(rules)

    sa = by_id.get("sw_route_auto")
    if not sa:
        raise SystemExit("sw_route_auto 없음")
    arules = sa.get("rules") or []
    awires = sa.get("wires") or []
    if any(r.get("v") == "auto_led_b2" for r in arules):
        pass
    else:
        aidx = next((i for i, r in enumerate(arules) if r.get("v") == "auto_led_b1"), None)
        if aidx is None:
            raise SystemExit("sw_route_auto: auto_led_b1 없음")
        insert_a = aidx + 1
        arules.insert(insert_a, {"t": "eq", "v": "auto_led_b2", "vt": "str"})
        awires.insert(insert_a, [])
        sa["rules"] = arules
        sa["wires"] = awires
        sa["outputs"] = len(arules)

    DASH.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("OK", DASH, "LED B2 모니터 토글 + tele/cmd/스위치")


if __name__ == "__main__":
    main()
