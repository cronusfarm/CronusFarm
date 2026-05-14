# -*- coding: utf-8 -*-
"""이전에 삭제된 _apply_monitor_settings_ui.py: 대시보드 JSON을 일회성으로 덮어쓰던 스크립트였음.
현재 저장소는 이 파일로 CSS 깨짐·차트·게이지만 보정한다."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
DEV = ROOT / "nodered" / "flows_cronusfarm_devflow_flow.json"


def fix_gh_gauges_tab_z(data: list) -> int:
    """온실 Data(ui_grp_gh_data) 게이지·차트가 PHW3988 탭 z에 묶이면 모니터 카드에 안 보일 수 있어 tab_cronus_dash 로 통일."""
    nchg = 0
    for n in data:
        if n.get("group") != "ui_grp_gh_data":
            continue
        if n.get("type") not in ("ui_gauge", "ui_chart"):
            continue
        if n.get("z") != "tab_cronus_dash":
            n["z"] = "tab_cronus_dash"
            nchg += 1
    return nchg


def patch_dashboard(data: list) -> int:
    nchg = 0
    nchg += fix_gh_gauges_tab_z(data)
    for n in data:
        nid = n.get("id")
        if nid == "ui_tpl_css_cronus" and n.get("type") == "ui_template":
            fmt = n.get("format") or ""
            old = fmt
            # 중간에 끊긴 </style> 제거(이후 블록은 동일 스타일 시트에 포함)
            bad = "</style>\n\n/* 펌프 가드(G:) 카드:"
            if bad in fmt:
                fmt = fmt.replace(bad, "\n\n/* 펌프 가드(G:) 카드:", 1)
                nchg += 1
            fmt = fmt.rstrip()
            if not fmt.endswith("</style>"):
                fmt = fmt + "\n</style>"
                nchg += 1
            inj = """

/* 히스토그램: maintainAspectRatio=false 시 부모 높이 0으로 캔버스가 사라지는 문제 완화 */
.nr-dashboard-theme .cf-hist-box{
  position:relative;
  min-height:72px;
  box-sizing:border-box;
}
.nr-dashboard-theme .cf-hist-combo{
  min-height:150px;
}
/* 온실 게이지: 어두운 카드에서 눈금·숫자 대비 */
.nr-dashboard-theme .cf-gh-data-dark .nr-dashboard-gauge,
.nr-dashboard-theme .cf-gh-data-dark .nr-dashboard-gauge text,
.nr-dashboard-theme .cf-gh-data-dark .nr-dashboard-gauge .gaugeValue,
.nr-dashboard-theme .cf-gh-data-dark .nr-dashboard-gauge .gauge-label{
  color:#e6edf7 !important;
  fill:#e6edf7 !important;
}
"""
            if "cf-hist-combo{" not in fmt:
                if fmt.rstrip().endswith("</style>"):
                    core = fmt.rstrip()[:-8].rstrip()
                    fmt = core + inj + "\n</style>"
                    nchg += 1
            if fmt != old:
                n["format"] = fmt
        if n.get("type") == "ui_template" and "format" in n:
            fmt = n.get("format") or ""
            if "new Chart(" in fmt and "maintainAspectRatio: false" in fmt:
                n["format"] = fmt.replace(
                    "maintainAspectRatio: false",
                    "maintainAspectRatio: true",
                    1,
                )
                nchg += 1
            if nid in ("ui_tpl_hist_combo_a", "ui_tpl_hist_combo_b"):
                if '<div class="cf-hist-box"' in fmt and "cf-hist-combo" not in fmt:
                    n["format"] = fmt.replace(
                        '<div class="cf-hist-box"',
                        '<div class="cf-hist-box cf-hist-combo"',
                        1,
                    )
                    nchg += 1
                if n.get("height") != 5:
                    n["height"] = 5
                    nchg += 1
    return nchg


def patch_devflow(data: list) -> int:
    nchg = fix_gh_gauges_tab_z(data)
    for n in data:
        if n.get("type") == "ui_gauge" and n.get("group") == "ui_grp_gh_data":
            if n.get("width") != 4 or n.get("height") != 3:
                n["width"] = 4
                n["height"] = 3
                nchg += 1
            if n.get("className"):
                n["className"] = ""
                nchg += 1
    return nchg


def main() -> None:
    d1 = json.loads(DASH.read_text(encoding="utf-8-sig"))
    c1 = patch_dashboard(d1)
    DASH.write_text(json.dumps(d1, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    d2 = json.loads(DEV.read_text(encoding="utf-8-sig"))
    c2 = patch_devflow(d2)
    DEV.write_text(json.dumps(d2, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print(f"OK dashboard patches={c1}, devflow gauge patches={c2}")


if __name__ == "__main__":
    main()
