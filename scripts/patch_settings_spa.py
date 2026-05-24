# -*- coding: utf-8 -*-
"""D1 설정 탭: 링크 카드 제거 → /farm/ui/#/beds 로 즉시 이동."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

# hash 라우터: nginx·Node-RED httpStatic 모두에서 하위 경로 404 없이 동작
SPA_ENTRY = "/farm/ui/#/"

SPA_REDIRECT = f"""<script type="text/javascript">
(function(){{
  var u = (window.location.origin || '') + '{SPA_ENTRY}';
  var p = window.location.pathname || '';
  if (p.indexOf('/farm/ui') === 0) return;
  var w = window.top || window;
  try {{ w.location.replace(u); }} catch (e) {{ w.location.href = u; }}
}})();
</script>"""

IFRAME_IDS = (
    "ui_tpl_settings_beds_iframe",
    "ui_tpl_settings_sched_ov_iframe",
    "ui_tpl_settings_tools_iframe",
)


def main() -> int:
    raw: list = json.loads(DASH.read_text(encoding="utf-8-sig"))
    by: dict[str, dict] = {n["id"]: n for n in raw if isinstance(n, dict) and n.get("id")}

    arch = by.get("ui_tpl_settings_arch")
    if isinstance(arch, dict):
        arch["disabled"] = True
        arch["height"] = 1

    first = True
    for tid in IFRAME_IDS:
        n = by.get(tid)
        if not isinstance(n, dict):
            continue
        if first:
            n["format"] = SPA_REDIRECT
            n["name"] = "설정 → SPA 이동"
            n["height"] = 4
            n["group"] = "ui_grp_settings_beds"
            n["disabled"] = False
            first = False
        else:
            n["disabled"] = True
            n["format"] = "<!-- SPA redirect: ui_tpl_settings_beds_iframe -->"
            n["height"] = 1

    for gid, name, disabled in (
        ("ui_grp_settings_beds", "설정", False),
        ("ui_grp_settings_sched_ov", "", True),
        ("ui_grp_settings_tools", "", True),
    ):
        g = by.get(gid)
        if not isinstance(g, dict):
            continue
        c = (g.get("className") or "").strip()
        if "cf-monitor-grp" not in c.split():
            g["className"] = f"{c} cf-monitor-grp".strip()
        if name:
            g["name"] = name
        g["disabled"] = disabled

    DASH.write_text(json.dumps(list(by.values()), ensure_ascii=False), encoding="utf-8")
    print(f"OK patch_settings_spa (D1 설정 탭 → {SPA_ENTRY})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
