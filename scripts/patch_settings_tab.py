# -*- coding: utf-8 -*-
"""설정 탭: 기획 반영(iframe·C/D Bed·흐름 안내 패널)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
BEDS_HTML = ROOT / "nodered" / "dashboard" / "cronusfarm_d1_settings_beds_sched.html"
TOOLS_HTML = ROOT / "nodered" / "dashboard" / "cronusfarm_d1_settings_tools.html"

SHARED_CSS_HREF = "/cronusfarm-static/cronusfarm_d1_shared.css"
MONITOR_GROUP_CLASS = "cf-monitor-grp"

SETTINGS_TAB_CSS = """
/* 설정 탭: 모니터와 동일 온실 배경·카드 (공통 토큰) */
body.nr-dashboard-theme md-content{
  background:linear-gradient(180deg,var(--g0,#040d07) 0%,var(--cf-bg,#0a1a0f) 60%,var(--g0,#040d07) 100%)!important;
  color:var(--cf-text,#c8e6c9)!important;
}
.nr-dashboard-theme .nr-dashboard-group.cf-monitor-grp .nr-dashboard-cardpanel,
.nr-dashboard-theme .nr-dashboard-group.cf-monitor-grp .nr-dashboard-template{
  background:var(--cf-card,rgba(10,26,15,.9))!important;
  border:1px solid var(--border,rgba(45,255,122,.07))!important;
  box-shadow:var(--glow,0 0 28px rgba(45,255,122,.07))!important;
}
"""

SETTINGS_ARCH = f"""<link rel="stylesheet" href="{SHARED_CSS_HREF}">
<div class="cf-settings-arch">
<h4>설정 흐름(축약)</h4>
<p>아래 <strong>Bed·스케줄</strong>에서 채널 수동/자동·스케줄 저장 → SQLite <code>schedule_rule</code> → MQTT <code>SCHED_JSON</code> → Arduino → tele → <code>tele_channel_fact</code> → <strong>모니터 타임라인</strong>에 반영됩니다.</p>
<p><strong>스케줄 API·관제</strong> 그룹: REST 디버그·KV·감사 로그 조회. cmd·tele 로직은 MQTT 탭 단일 경로(이중 Function 금지).</p>
</div>"""

IFRAME_CSS = (
    f'<link rel="stylesheet" href="{SHARED_CSS_HREF}">\n'
    "<style>/* 설정 탭 iframe: 박스 내부 스크롤 제거, 높이는 콘텐츠에 맞춤 */\n"
    "body.nr-dashboard-theme .nr-dashboard-template:has(.cf-settings-iframe-wrap),\n"
    "body.nr-dashboard-theme .nr-dashboard-template:has(.cf-settings-iframe-wrap) md-card-content,\n"
    "body.nr-dashboard-theme md-card:has(.cf-settings-iframe-wrap) md-card-content{\n"
    "  overflow:visible!important;max-height:none!important;height:auto!important;}\n"
    ".nr-dashboard-theme .nr-dashboard-group:has(.cf-settings-iframe-wrap) md-card,\n"
    ".nr-dashboard-theme .nr-dashboard-group:has(.cf-settings-iframe-wrap) md-card-content{\n"
    "  overflow:visible!important;}\n"
    ".cf-settings-iframe-wrap{width:100%;box-sizing:border-box;border-radius:12px;overflow:visible;\n"
    "  border:1px solid rgba(45,255,122,.12);background:rgba(0,0,0,.2);}\n"
    ".cf-settings-iframe-wrap iframe{display:block;width:100%;min-height:400px;height:400px;border:0;"
    "background:var(--g0,#040d07);overflow:hidden;}\n"
    + SETTINGS_TAB_CSS
    + "\n</style>"
)

IFRAME_RESIZE_JS = """<script type="text/javascript">
(function(){
  window.addEventListener('message',function(ev){
    var d=ev.data;
    if(!d||d.type!=='cf-settings-iframe-resize'||!d.height)return;
    var h=Math.max(320,parseInt(d.height,10)+24)+'px';
    var id=d.iframe||'';
    document.querySelectorAll('.cf-settings-iframe-wrap').forEach(function(wrap){
      var ifr=wrap.querySelector('iframe');
      if(!ifr)return;
      if(id){ if(wrap.getAttribute('data-cf-iframe')===id) ifr.style.height=h; return; }
      if(ev.source&&ifr.contentWindow===ev.source) ifr.style.height=h;
    });
  },false);
})();
</script>"""


def _ensure_shared_css_link(fmt: str) -> str:
    """D1 전역 CSS 템플릿에 공통 토큰 파일 링크."""
    if SHARED_CSS_HREF in fmt:
        return fmt
    link = f'<link rel="stylesheet" href="{SHARED_CSS_HREF}">\n'
    if fmt.lstrip().startswith("<style"):
        return link + fmt
    return link + fmt


def _alias_dashboard_root_tokens(fmt: str) -> str:
    """ui_tpl_css_cronus :root 를 온실 공통 토큰에 맞춤(기존 규칙은 유지)."""
    old_root = """:root{
  --cf-bg:#0b1220;
  --cf-card:#0f1b31;
  --cf-text:#e6edf7;
  --cf-muted:#9db0cc;
  --cf-accent:#4f8cff;
  --cf-title:#FFD54F;
  --cf-pad-x:14px;
  --cf-pad-y:16px;
}"""
    new_root = """:root{
  --cf-bg:var(--g1,#0a1a0f);
  --cf-card:var(--card,rgba(10,26,15,.9));
  --cf-text:var(--text,#c8e6c9);
  --cf-muted:var(--text2,#6b9c73);
  --cf-accent:var(--accent,#2dff7a);
  --cf-title:var(--accent3,#ffb830);
  --cf-pad-x:14px;
  --cf-pad-y:16px;
}"""
    if old_root in fmt:
        return fmt.replace(old_root, new_root, 1)
    return fmt


def patch_settings_groups(by: dict[str, dict]) -> None:
    """설정 탭 ui_group → 모니터와 동일 cf-monitor-grp (제목줄 CSS 공유)."""
    for gid in ("ui_grp_settings_beds", "ui_grp_settings_tools"):
        g = by.get(gid)
        if not isinstance(g, dict):
            continue
        c = (g.get("className") or "").strip()
        if MONITOR_GROUP_CLASS not in c.split():
            g["className"] = f"{c} {MONITOR_GROUP_CLASS}".strip()


def patch_global_css(by: dict[str, dict]) -> None:
    n = by.get("ui_tpl_css_cronus")
    if not isinstance(n, dict):
        return
    fmt = _ensure_shared_css_link(n.get("format") or "")
    fmt = _alias_dashboard_root_tokens(fmt)
    n["format"] = fmt


def patch_beds_html() -> None:
    txt = BEDS_HTML.read_text(encoding="utf-8")
    if "pump_c1" in txt and "C Bed" in txt:
        return
    insert = """
        { id: 'C', title: 'C Bed', channels: [
          { key: 'pump_c1', label: 'Pump C1', pin: 'R4-A0', kind: 'pump' },
          { key: 'pump_c2', label: 'Pump C2', pin: 'R4-A1', kind: 'pump' },
        ]},
        { id: 'D', title: 'D Bed', channels: [
          { key: 'pump_d1', label: 'Pump D1', pin: 'R4-A2', kind: 'pump' },
          { key: 'pump_d2', label: 'Pump D2', pin: 'R4-A3', kind: 'pump' },
        ]},"""
    marker = "        ]},\n      ],\n      schChannel:"
    if marker not in txt:
        raise SystemExit("beds 배열 마커 없음")
    txt = txt.replace(
        "        ]},\n      ],\n      schChannel:",
        "        ]}," + insert + "\n      ],\n      schChannel:",
        1,
    )
    BEDS_HTML.write_text(txt, encoding="utf-8")


def patch_settings_html_shared_css() -> None:
    """설정 iframe HTML: 중복 :root 제거, 공통 CSS 링크."""
    link = f'  <link rel="stylesheet" href="{SHARED_CSS_HREF}"/>\n'
    for path in (
        BEDS_HTML,
        TOOLS_HTML,
    ):
        txt = path.read_text(encoding="utf-8")
        if SHARED_CSS_HREF in txt and ":root{" not in txt.split("</head>", 1)[0]:
            continue
        if SHARED_CSS_HREF not in txt:
            txt = txt.replace("<head>\n", "<head>\n" + link, 1)
        txt = re.sub(
            r"\s*<style>\s*/\*[^*]*\*/\s*:root\{[\s\S]*?\}\s*",
            "\n  <style>\n    /* 페이지 전용 — 토큰은 cronusfarm_d1_shared.css */\n    ",
            txt,
            count=1,
        )
        txt = re.sub(r"\s*<style>\s*:root\{[\s\S]*?\}\s*", "\n  <style>\n    ", txt, count=1)
        path.write_text(txt, encoding="utf-8")


def ensure_settings_nodes(by: dict[str, dict]) -> None:
    grp_beds = "ui_grp_settings_beds"
    grp_tools = "ui_grp_settings_tools"

    by["ui_tpl_settings_arch"] = {
        "id": "ui_tpl_settings_arch",
        "type": "ui_template",
        "z": "tab_cronus_dash",
        "group": grp_beds,
        "name": "설정 탭 안내",
        "order": 0,
        "width": "12",
        "height": 3,
        "format": SETTINGS_ARCH,
        "storeOutMessages": False,
        "fwdInMessages": False,
        "resendOnRefresh": True,
        "templateScope": "local",
        "x": 100,
        "y": 1100,
        "wires": [[]],
    }

    for tid, src, title, h in (
        (
            "ui_tpl_settings_beds_iframe",
            "/cronusfarm-static/cronusfarm_d1_settings_beds_sched.html",
            "Bed/스케줄 (iframe)",
            72,
        ),
        (
            "ui_tpl_settings_tools_iframe",
            "/cronusfarm-static/cronusfarm_d1_settings_tools.html",
            "스케줄 API·관제 (iframe)",
            56,
        ),
    ):
        fmt = (
            f'<div class="cf-settings-iframe-wrap"><iframe title="{title}" loading="lazy" '
            f'scrolling="no" sandbox="allow-scripts allow-same-origin allow-forms allow-popups" '
            f'src="{src}"></iframe></div>'
            + IFRAME_CSS
            + IFRAME_RESIZE_JS
        )
        n = by.get(tid)
        if not isinstance(n, dict):
            n = {
                "id": tid,
                "type": "ui_template",
                "z": "tab_cronus_dash",
                "group": grp_beds if "beds" in tid else grp_tools,
                "name": title,
                "order": 1,
                "width": "12",
                "height": h,
                "storeOutMessages": False,
                "fwdInMessages": False,
                "resendOnRefresh": True,
                "templateScope": "local",
                "x": 100,
                "y": 1200,
                "wires": [[]],
            }
            by[tid] = n
        n["format"] = fmt
        n["order"] = 1
        n["group"] = grp_beds if "beds" in tid else grp_tools

    for gid, name, order in (
        (grp_beds, "Bed 제어 · 스케줄", 1),
        (grp_tools, "스케줄 API · 관제 허브", 2),
    ):
        g = by.get(gid)
        if isinstance(g, dict):
            g["tab"] = "ui_tab_settings"
            g["name"] = name
            g["order"] = order
            g["width"] = "12"


def main() -> int:
    patch_beds_html()
    patch_settings_html_shared_css()
    raw: list = json.loads(DASH.read_text(encoding="utf-8-sig"))
    by: dict[str, dict] = {n["id"]: n for n in raw if isinstance(n, dict) and n.get("id")}
    ensure_settings_nodes(by)
    patch_settings_groups(by)
    patch_global_css(by)
    DASH.write_text(json.dumps(list(by.values()), ensure_ascii=False), encoding="utf-8")
    print("OK settings tab (shared CSS, cf-monitor-grp, iframes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
