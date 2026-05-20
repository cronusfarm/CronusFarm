#!/usr/bin/env python3
"""
Dashboard 1 (/ui) 상단 하늘색 메뉴바(md-toolbar#toolbar) 높이만 축소.

- 햄버거(삼선) 오른쪽 메뉴명이 있는 상단 툴바만 대상
- 좌측 드로어(md-sidenav) / ui_base sy·sx / Bed 그리드는 건드리지 않음
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

DASH1_BLOCK = re.compile(r"/\* Dashboard 1:.*?(?=\n\n</style>)", re.DOTALL)

# 상단 #toolbar 축소 + 드로어(md-sidenav) top 정렬만 (항목 높이·sy/sx 는 변경 없음)
DASH1_CSS = """/* Dashboard 1: 상단 하늘색 메뉴바(#toolbar) 줄 높이 + 드로어 위치 정렬 */
body.nr-dashboard-theme{
  --cf-d1-toolbar-h: 32px;
}
body.nr-dashboard-theme md-toolbar#toolbar{
  min-height: var(--cf-d1-toolbar-h) !important;
  height: var(--cf-d1-toolbar-h) !important;
  max-height: 36px !important;
}
body.nr-dashboard-theme md-toolbar#toolbar .md-toolbar-tools{
  min-height: 28px !important;
  height: 28px !important;
  max-height: 32px !important;
  padding-top: 0 !important;
  padding-bottom: 0 !important;
}
body.nr-dashboard-theme md-toolbar#toolbar .md-button,
body.nr-dashboard-theme md-toolbar#toolbar .md-icon-button{
  min-height: 28px !important;
  height: 28px !important;
  width: 28px !important;
  min-width: 28px !important;
  line-height: 28px !important;
  margin: 0 2px !important;
  padding: 0 !important;
}
body.nr-dashboard-theme md-toolbar#toolbar h1,
body.nr-dashboard-theme md-toolbar#toolbar .md-title,
body.nr-dashboard-theme md-toolbar#toolbar .md-toolbar-tools-title{
  margin: 0 !important;
  padding: 0 8px !important;
  line-height: 28px !important;
  font-size: 14px !important;
  font-weight: 600 !important;
}
/* 햄버거(삼선) 열림: 축소된 툴바 바로 아래에 붙임 — 위쪽 한 줄 빈틈 제거 */
body.nr-dashboard-theme md-sidenav,
body.nr-dashboard-theme md-sidenav.md-sidenav-left{
  top: var(--cf-d1-toolbar-h) !important;
  height: calc(100% - var(--cf-d1-toolbar-h)) !important;
  max-height: calc(100% - var(--cf-d1-toolbar-h)) !important;
}
body.nr-dashboard-theme md-sidenav md-content,
body.nr-dashboard-theme md-sidenav > md-content{
  padding-top: 0 !important;
  margin-top: 0 !important;
}
body.nr-dashboard-theme md-sidenav md-list{
  padding-top: 0 !important;
  margin-top: 0 !important;
}
"""


def patch() -> None:
    data = json.loads(DASH.read_text(encoding="utf-8-sig"))
    changed = False

    for n in data:
        if n.get("id") == "ui_tpl_css_cronus":
            fmt = n.get("format", "")
            if DASH1_BLOCK.search(fmt):
                fmt = DASH1_BLOCK.sub(DASH1_CSS, fmt, count=1)
                changed = True
                print("OK ui_tpl_css_cronus: #toolbar + md-sidenav top 정렬")
            elif "--cf-d1-toolbar-h" not in fmt:
                ins = fmt.find("</style>")
                if ins >= 0:
                    fmt = fmt[:ins] + "\n" + DASH1_CSS + "\n" + fmt[ins:]
                    changed = True
                    print("OK ui_tpl_css_cronus: 상단 #toolbar CSS 추가")
            if changed:
                n["format"] = fmt

    if not changed:
        print("WARN: 변경 없음")
        return

    DASH.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    merge = ROOT / "scripts" / "merge_nodered_deploy.py"
    if merge.is_file():
        r = subprocess.run(
            [sys.executable, str(merge), "--use-split"],
            cwd=str(ROOT),
        )
        if r.returncode != 0:
            raise SystemExit("merge_nodered_deploy.py 실패")


if __name__ == "__main__":
    patch()
