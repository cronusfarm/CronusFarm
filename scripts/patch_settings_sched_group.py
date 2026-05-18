# -*- coding: utf-8 -*-
"""설정 탭: 채널별 24h 스케줄을 Bed와 동급 ui_group 카드로 분리."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
TOOLS = ROOT / "nodered/dashboard/cronusfarm_d1_settings_tools.html"

GRP_ID = "ui_grp_settings_sched_ov"
TPL_ID = "ui_tpl_settings_sched_ov_iframe"
SRC = "/cronusfarm-static/cronusfarm_d1_settings_sched_overview.html"


def strip_tools_overview() -> None:
    txt = TOOLS.read_text(encoding="utf-8")
    if "mount-sch-overview" not in txt:
        return
    import re

    txt = re.sub(r"\n    \.cf-sch-overview\{[\s\S]*?\.cf-sch-overview-foot\{[^\}]+\}\n", "\n", txt, count=1)
    txt = re.sub(
        r"\n  <motion id=\"mount-sch-overview\"></div>\n  <hr[^>]+/>\n",
        "\n",
        txt,
    )
    txt = re.sub(
        r"\n  <div id=\"mount-sch-overview\"></motion>\n  <hr[^>]+/>\n",
        "\n",
        txt,
    )
    txt = re.sub(
        r"function cfTimeStrToMin[\s\S]*?Vue\.createApp\(SchOverviewApp\)\.mount\('#mount-sch-overview'\);\n",
        "",
        txt,
        count=1,
    )
    if "window.addEventListener('message'" not in txt and "cf-sch-goto" in txt:
        pass
    listener = """
window.addEventListener('message', function(ev) {
  var d = ev.data;
  if (!d || d.type !== 'cf-sch-goto' || !d.channel || !window.__cfScheduleVm) return;
  window.__cfScheduleVm.channel = d.channel;
  window.__cfScheduleVm.loadSch();
  try { document.getElementById('cf-sch-device-id').value = window.__cfScheduleVm.deviceId; } catch (e) {}
});
"""
    if "d.type !== 'cf-sch-goto'" not in txt:
        txt = txt.replace(
            "ScheduleApp.template = '#tpl-schedule';",
            listener + "ScheduleApp.template = '#tpl-schedule';",
            1,
        )
    txt = re.sub(
        r"window\.addEventListener\('cf-sch-goto'[\s\S]*?\}\);\n",
        "",
        txt,
        count=1,
    )
    TOOLS.write_text(txt, encoding="utf-8")
    print("OK tools.html overview removed")


def patch_dashboard() -> None:
    sys.path.insert(0, str(ROOT))
    from scripts.patch_settings_tab import IFRAME_CSS, IFRAME_RESIZE_JS, MONITOR_GROUP_CLASS

    data = json.loads(DASH.read_text(encoding="utf-8-sig"))
    by = {n["id"]: n for n in data if isinstance(n, dict) and n.get("id")}

    if GRP_ID not in by:
        data.append(
            {
                "id": GRP_ID,
                "type": "ui_group",
                "name": "채널별 스케줄 (0:00–24:00 · 전체)",
                "tab": "ui_tab_settings",
                "order": 2,
                "disp": True,
                "width": "12",
                "collapse": False,
                "className": MONITOR_GROUP_CLASS,
            }
        )
    else:
        g = by[GRP_ID]
        g["name"] = "채널별 스케줄 (0:00–24:00 · 전체)"
        g["order"] = 2
        g["tab"] = "ui_tab_settings"

    g_tools = by.get("ui_grp_settings_tools")
    if isinstance(g_tools, dict):
        g_tools["order"] = 3

    fmt = (
        f'<motion class="cf-settings-iframe-wrap"><iframe title="스케줄 24h 전체" loading="lazy" '
        f'scrolling="no" sandbox="allow-scripts allow-same-origin allow-forms allow-popups" '
        f'src="{SRC}"></iframe></div>'
        + IFRAME_CSS
        + IFRAME_RESIZE_JS
    ).replace("<motion", "<div").replace("</motion>", "</div>")

    n = by.get(TPL_ID)
    if not isinstance(n, dict):
        n = {
            "id": TPL_ID,
            "type": "ui_template",
            "z": "tab_cronus_dash",
            "group": GRP_ID,
            "name": "스케줄 24h 전체 (iframe)",
            "order": 1,
            "width": "12",
            "height": 48,
            "storeOutMessages": False,
            "fwdInMessages": False,
            "resendOnRefresh": True,
            "templateScope": "local",
            "x": 100,
            "y": 1250,
            "wires": [[]],
        }
        data.append(n)
    n["format"] = fmt
    n["group"] = GRP_ID
    n["height"] = 48

    DASH.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print("OK patch_settings_sched_group (dashboard)")


def main() -> None:
    strip_tools_overview()
    patch_dashboard()
    merge = ROOT / "scripts" / "merge_nodered_deploy.py"
    if merge.is_file():
        r = subprocess.run([sys.executable, str(merge), "--use-split"], cwd=str(ROOT))
        if r.returncode != 0:
            raise SystemExit("merge 실패")


if __name__ == "__main__":
    main()
