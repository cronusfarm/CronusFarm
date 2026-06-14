# -*- coding: utf-8 -*-
"""D1 설정 탭 → /farm/ui/ 전체 이동 (iframe 없음)."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
INDEX = ROOT / "nodered" / "dashboard" / "index.html"

SPA_ENTRY = "/farm/ui/#/"

# D1 위젯: 즉시 farm-ui로 이동 (iframe 금지)
SPA_REDIRECT_ONLY = f"""<div data-cf-settings-spa="1" style="display:none!important;height:0!important;overflow:hidden!important"></div>
<script type="text/javascript">
(function(){{
  var u=(location.origin||'')+'{SPA_ENTRY}';
  try{{(window.top||window).location.replace(u);}}catch(e){{location.href=u;}}
}})();
</script>"""

SETTINGS_GLOBAL_CSS = """
.nr-dashboard-theme md-content:has([data-cf-settings-spa]) .nr-dashboard-group,
.nr-dashboard-theme [ui-view*="settings"] .nr-dashboard-group {
  display:none!important;height:0!important;overflow:hidden!important;
}
"""

DROP_GROUP_IDS = frozenset(
    {
        "ui_grp_settings_sched_ov",
        "ui_grp_settings_tools",
    }
)
DROP_NODE_IDS = frozenset(
    {
        "ui_tpl_settings_beds_iframe",
        "ui_tpl_settings_sched_ov_iframe",
        "ui_tpl_settings_tools_iframe",
    }
)


def _patch_index_html() -> None:
    if not INDEX.is_file():
        return
    txt = INDEX.read_text(encoding="utf-8")
    if "cfGoSettingsSpa" in txt and "location.replace" in txt:
        return
    block = f"""    <script type="text/javascript">
      (function () {{
        var SPA = (location.origin || '') + '{SPA_ENTRY}';
        function cfIsSettingsTab() {{
          var h = location.hash || '';
          return h.indexOf('ui-tab_settings') >= 0 || h === '#/1' || h.indexOf('#/1/') === 0;
        }}
        function cfGoSettingsSpa() {{
          if (!cfIsSettingsTab()) return;
          try {{ (window.top || window).location.replace(SPA); }}
          catch (e) {{ location.href = SPA; }}
        }}
        if (!window.__cfSettingsSpaBoot) {{
          window.__cfSettingsSpaBoot = 1;
          cfGoSettingsSpa();
          window.addEventListener('hashchange', cfGoSettingsSpa);
        }}
      }})();
    </script>"""
    if "ui-tab_settings" in txt and "cfGoSettingsSpa" not in txt:
        txt = txt.replace(
            "<!-- 설정 탭:",
            block + "\n    <!-- 설정 탭:",
            1,
        )
    elif "D1 iframe" in txt or "리다이렉트 없음" in txt:
        txt = re.sub(
            r"<!-- 설정 탭:[\s\S]*?</script>\s*",
            block + "\n    ",
            txt,
            count=1,
        )
    INDEX.write_text(txt, encoding="utf-8")
    print("OK index.html → farm-ui redirect (no iframe)")


def main() -> int:
    raw: list = json.loads(DASH.read_text(encoding="utf-8-sig"))
    out: list = []
    for n in raw:
        if not isinstance(n, dict):
            out.append(n)
            continue
        nid = n.get("id")
        grp = n.get("group")
        if nid in DROP_NODE_IDS or grp in DROP_GROUP_IDS or nid in DROP_GROUP_IDS:
            continue
        out.append(n)

    by = {n["id"]: n for n in out if n.get("id")}

    arch = by.get("ui_tpl_settings_arch")
    if arch:
        arch["format"] = SPA_REDIRECT_ONLY
        arch["name"] = "→ farm-ui"
        arch["height"] = 1
        arch["order"] = 0
        arch["disabled"] = False
        arch["group"] = "ui_grp_settings_beds"

    g = by.get("ui_grp_settings_beds")
    if g:
        g["name"] = "설정"
        g["order"] = 1
        g["disabled"] = False
        g["disp"] = False
        g["width"] = "12"
        g["collapse"] = True

    tab = by.get("ui_tab_settings")
    if tab:
        tab["name"] = "설정"

    css = by.get("ui_tpl_css_cronus")
    if css:
        fmt = css.get("format") or ""
        if SETTINGS_GLOBAL_CSS.strip() not in fmt:
            ins = fmt.find("</style>")
            if ins >= 0:
                fmt = fmt[:ins] + SETTINGS_GLOBAL_CSS + fmt[ins:]
            else:
                fmt += f"<style>{SETTINGS_GLOBAL_CSS}</style>"
        css["format"] = fmt

    DASH.write_text(json.dumps(list(by.values()), ensure_ascii=False), encoding="utf-8")
    _patch_index_html()
    print(f"OK patch_settings_spa: redirect only → {SPA_ENTRY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
