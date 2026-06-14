# -*- coding: utf-8 -*-
"""개발현황: 설정 탭과 동일 D1 셸(공통 CSS·햄버거 메뉴·iframe) + 본문 섹션 정적 HTML."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEVFLOW = ROOT / "nodered" / "flows_cronusfarm_devflow_flow.json"
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
HTML_OUT = ROOT / "nodered" / "dashboard" / "cronusfarm_d1_devflow.html"
BOOT_DOC = ROOT / "nodered" / "dashboard" / "cronusfarm_panel_lcd_boot.html"
FLOW_TARGETS = [
    DEVFLOW,
    DASH,
    ROOT / "nodered" / "merged-deploy.json",
    ROOT / "nodered" / "CronusFarm_NodeRED_flow.json",
]

SHARED_CSS = "/cronusfarm-static/cronusfarm_d1_shared.css"
MONITOR_GROUP_CLASS = "cf-monitor-grp"
TAB_DEV = "ui_tab_devflow"
GRP_MAIN = "ui_grp_devflow"
TPL_IFRAME = "ui_tpl_devflow_main_iframe"
TPL_LAYOUT = "ui_tpl_devflow_layout_css"
HIDDEN_STUB = '<div class="cf-dev-merged-hidden" aria-hidden="true" style="display:none!important"></div>'

# 메뉴 순서 = NR #!/4 ui_template order (layout CSS 제외, 0부터 번호)
MENU: list[tuple[str, str, str]] = [
    ("sec-local", "개발현황 · 보는 방법", "ui_tpl_devflow_local_banner"),
    ("sec-overview", "시스템 개요 · 순서도", "ui_tpl_devflow_diagram"),
    ("sec-devdeploy", "플로우(개발·배포)", "ui_tpl_devflow_flow_devdeploy"),
    ("sec-camera-pipe", "카메라 파이프라인", "ui_tpl_devflow_camera_pipeline"),
    ("sec-camera-tbl", "카메라 · 용량", "ui_tpl_devflow_camera_tables"),
    ("sec-hailo", "Hailo YOLO 학습", "ui_tpl_devflow_hailo_train"),
    ("sec-entity", "호스트 · 소스 · URL", "ui_tpl_devflow_entity"),
    ("sec-runtime", "플로우(운영)", "ui_tpl_devflow_flow_runtime"),
    ("sec-monitor-src", "모니터 데이터 출처", "ui_tpl_devflow_monitor_data_src"),
    ("sec-control", "제어 흐름(목표)", "ui_tpl_devflow_control_flow"),
    ("sec-comm-a", "통신 A · 하이브리드", "ui_tpl_cf_comm_20260525_01"),
    ("sec-comm-b", "통신 B · MQTT", "ui_tpl_cf_comm_20260525_02"),
    ("sec-comm-c", "통신 C · Pi", "ui_tpl_cf_comm_20260525_03"),
    ("sec-comm-d", "통신 D · USB", "ui_tpl_cf_comm_20260525_04"),
    ("sec-flow-data", "플로우(DB·연동)", "ui_tpl_devflow_flow_data"),
    ("sec-arch", "구성요소 · 데이터흐름", "ui_tpl_devflow_arch_full"),
    ("sec-nr-paths", "Node-RED 경로", "ui_tpl_devflow_nodered_paths"),
    ("sec-panel", "패널 LCD 가이드", "cf_tpl_dev_panel_usage"),
    ("sec-hw", "하드웨어 · 핀맵", "cf_tpl_dev_hw_panel"),
]

KEEP_TPL_IDS = frozenset({TPL_IFRAME, TPL_LAYOUT})
# iframe/static HTML 로 대체되는 개발현황 템플릿만 숨김 (모니터·설정 ui_template 건드리지 않음)
DEVFLOW_HIDE_TPL_IDS = frozenset(tid for _, _, tid in MENU)

DEVFLOW_TAB_CSS = """
/* 개발현황 탭 — 설정·모니터와 동일 온실 배경 */
body.nr-dashboard-theme md-tab-content[aria-label*="개발현황"],
body.nr-dashboard-theme md-tab-content[aria-label*="개발환경"],
body.nr-dashboard-theme md-tab-content[aria-label*="개발"] md-content{
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

IFRAME_CSS = (
    f'<link rel="stylesheet" href="{SHARED_CSS}">\n'
    "<style>\n"
    "body.nr-dashboard-theme .nr-dashboard-template:has(.cf-devflow-iframe-wrap),\n"
    "body.nr-dashboard-theme .nr-dashboard-template:has(.cf-devflow-iframe-wrap) md-card-content{\n"
    "  overflow:visible!important;max-height:none!important;height:auto!important;}\n"
    ".cf-devflow-iframe-wrap{display:block!important;width:100%;box-sizing:border-box;border-radius:12px;"
    "overflow:visible;border:1px solid rgba(45,255,122,.12);background:rgba(0,0,0,.2);}\n"
    ".cf-devflow-iframe-wrap iframe{display:block;width:100%;min-height:520px;height:72vh;border:0;"
    "background:var(--g0,#040d07);overflow:hidden;}\n"
    + DEVFLOW_TAB_CSS
    + "\n</style>"
)

IFRAME_RESIZE_JS = """<script type="text/javascript">
(function(){
  window.addEventListener('message',function(ev){
    var d=ev.data;
    if(!d||d.type!=='cf-devflow-iframe-resize'||!d.height)return;
    var h=Math.max(400,parseInt(d.height,10)+24)+'px';
    var w=document.querySelector('.cf-devflow-iframe-wrap');
    if(w){var f=w.querySelector('iframe');if(f)f.style.height=h;}
  },false);
})();
</script>"""

IFRAME_FMT = (
    '<div class="cf-devflow-iframe-wrap" data-cf-devflow-iframe="1">'
    '<iframe title="CronusFarm 개발현황" loading="lazy" scrolling="no" '
    'sandbox="allow-scripts allow-same-origin allow-forms allow-popups" '
    f'src="/cronusfarm-static/cronusfarm_d1_devflow.html"></iframe></div>'
    + IFRAME_CSS
    + IFRAME_RESIZE_JS
)

LAYOUT_FMT = (
    f'<link rel="stylesheet" href="{SHARED_CSS}">\n<style>{DEVFLOW_TAB_CSS}</style>'
    '<div class="cf-dev-layout-only" aria-hidden="true" style="display:none"></div>'
)


def _strip_outer(html: str) -> str:
    """NR ui_template format 그대로 유지(style·래퍼 포함). 숨김 스텁만 제거."""
    html = html.strip()
    if not html:
        return ""
    if "merged-hidden" in html[:120] and len(html) < 200:
        return ""
    return html


def _hoist_styles(html: str) -> tuple[str, str]:
    """청크 내 <style> → page_css 로 올림(v-html 파싱 깨짐 방지)."""
    styles: list[str] = []

    def repl(m: re.Match[str]) -> str:
        styles.append(m.group(1).strip())
        return ""

    body = re.sub(r"<style[^>]*>(.*?)</style>", repl, html, flags=re.S | re.I)
    return body.strip(), "\n".join(styles)


def _sanitize_chunk_html(html: str) -> str:
    """Vue v-html 호환 — motion.div 등 비표준 태그 정리."""
    html = re.sub(r"<motion\.div\b", "<div", html, flags=re.I)
    html = re.sub(r"</motion\.div>", "</div>", html, flags=re.I)
    return html


def _load_boot_doc_body() -> str:
    if not BOOT_DOC.is_file():
        return ""
    text = BOOT_DOC.read_text(encoding="utf-8")
    m = re.search(r"<body[^>]*>(.*?)</body>", text, re.S | re.I)
    return m.group(1).strip() if m else ""


def _plain_text(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip()


def _wrap_hw_boot_fold(body: str, boot_body: str) -> str:
    """패널 LCD 표시 상태 — 부팅 순서 문서를 펼치기/접기."""
    if not boot_body:
        return body
    link = (
        r'<p style="margin:0 0 10px"><a href="/cronusfarm-static/cronusfarm_panel_lcd_boot\.html"[^>]*>'
        r"문서 열기 \(패널 부팅 순서\)</a></p>"
    )
    fold = (
        '<details class="cf-dev-fold cf-boot-fold">'
        "<summary>문서 열기 (패널 부팅 순서) — 펼치기</summary>"
        f'<div class="cf-dev-fold-body cf-boot-inline">{boot_body}</div>'
        "</details>"
    )
    return re.sub(link, fold, body, count=1)


_FOLD_H4 = re.compile(r"^[A-G]\.|^FAQ|^Node-RED / 동기", re.I)


def _wrap_cf_pu_h4_folds(body: str) -> str:
    """패널 LCD 전체 상태 — A~G·FAQ 등 긴 h4 소절 펼치기/접기."""
    m = re.search(r"(<div class=\"cf-pu\">)(.*?)(</div>\s*</div>\s*)$", body, re.S)
    if not m:
        return body
    inner = m.group(2)
    parts = re.split(r"(?=<h4>)", inner)
    out: list[str] = []
    for part in parts:
        if not part.strip():
            continue
        hm = re.match(r"<h4>(.*?)</h4>", part, re.S)
        if hm and _FOLD_H4.match(_plain_text(hm.group(1))):
            title = _plain_text(hm.group(1))
            rest = part[hm.end() :].strip()
            out.append(
                '<details class="cf-dev-fold cf-pu-fold">'
                f"<summary>{title} — 펼치기</summary>"
                f'<div class="cf-dev-fold-body">{rest}</div>'
                "</details>"
            )
        else:
            out.append(part)
    return m.group(1) + "".join(out) + m.group(3)


def _enhance_chunk_body(tid: str, body: str, boot_body: str) -> str:
    if tid == "cf_tpl_dev_panel_usage":
        body = _wrap_cf_pu_h4_folds(body)
    elif tid == "cf_tpl_dev_hw_panel":
        body = _wrap_hw_boot_fold(body, boot_body)
    return body


def _extract_layout_css(by: dict[str, dict]) -> str:
    n = by.get("ui_tpl_devflow_layout_css")
    if not n:
        return ""
    fmt = n.get("format") or ""
    m = re.search(r"<style>(.*?)</style>", fmt, re.S)
    return m.group(1).strip() if m else ""


def _build_devflow_html(by: dict[str, dict]) -> str:
    menu_li = "\n".join(
        f'        <button type="button" class="cf-drawer-item" data-cf-scroll="{sid}">{label}</button>'
        for sid, label, _ in MENU
    )
    chunks: list[str] = []
    embedded_css: list[str] = []
    boot_body = _load_boot_doc_body()
    for sid, _label, tid in MENU:
        n = by.get(tid)
        body = _strip_outer((n or {}).get("format") or "")
        if not body:
            continue
        body, css = _hoist_styles(body)
        if css:
            embedded_css.append(f"/* {tid} */\n{css}")
        body = _sanitize_chunk_html(body)
        body = _enhance_chunk_body(tid, body, boot_body)
        chunks.append(f'<div id="{sid}" class="cf-nr-chunk">{body}</div>')

    layout_css = _extract_layout_css(by)
    page_css = """
    html,body{min-height:100%;margin:0;background:#fff;color:#222;font-family:system-ui,'Malgun Gothic',sans-serif;overflow-x:hidden;}
    .cf-drawer-back{position:fixed;inset:0;z-index:200;background:rgba(0,0,0,.35);}
    .cf-drawer{position:fixed;top:0;left:0;bottom:0;z-index:210;width:min(280px,86vw);padding:14px 12px 20px;
      background:#fff;border-right:1px solid #e0e0e0;transform:translateX(-105%);transition:transform .22s ease;color:#222;}
    .cf-drawer.open{transform:translateX(0);}
    .cf-drawer-hd{margin:0 0 12px;padding-bottom:8px;border-bottom:1px solid #e0e0e0;font-size:11px;font-weight:800;color:#666;}
    .cf-drawer-sec-title{margin:14px 0 6px;font-size:11px;font-weight:800;color:#666;}
    .cf-drawer-item{display:block;width:100%;margin:0 0 6px;padding:11px 12px;border:1px solid transparent;border-radius:10px;
      background:transparent;color:#222;font-size:13px;font-weight:800;text-align:left;cursor:pointer;text-decoration:none;box-sizing:border-box;}
    .cf-drawer-item:hover{background:#f1f8f4;border-color:#c8e6c9;}
    .cf-settings-app{max-width:1120px;margin:0 auto;padding:12px;background:#fff;}
    .cf-settings-shell{position:relative;background:#fff;border:none;box-shadow:none;
      padding:14px 16px 24px;overflow:visible;color:#222;}
    .cf-settings-shell::before{display:none;}
    .cf-settings-shell>*{position:relative;z-index:1;}
    .cf-dev-lead{margin:0 0 16px;font-size:12px;color:#555;line-height:1.55;}
    /* 섹션 — 박스 없음, 구분선만 */
    .cf-nr-chunk{margin:0 0 24px;padding:0 0 20px;border-bottom:1px solid #e0e0e0;
      overflow:visible;background:none!important;border-radius:0!important;box-shadow:none!important;color:#222;}
    .cf-nr-chunk:last-child{border-bottom:none;margin-bottom:0;padding-bottom:0;}
    .cf-nr-chunk .cf-doc-h,.cf-nr-chunk .sec-h{display:flex;align-items:center;gap:10px;
      margin:0 0 12px;font-size:1.05rem;font-weight:800;color:#111;}
    .cf-nr-chunk .ch-n,.cf-nr-chunk .sec-n{flex:0 0 26px;width:26px;height:26px;border-radius:50%;
      background:#2e7d32;color:#fff;font-size:11px;font-weight:800;line-height:26px;text-align:center;
      display:inline-flex;align-items:center;justify-content:center;}
    .cf-nr-chunk section.cf-doc-sec{margin:0;padding:0;border:none;background:none!important;}
    .cf-nr-chunk .cf-pu-scroll,.cf-nr-chunk .flow-panel{max-height:none!important;overflow:visible!important;}
    /* 본문 박스 제거 — 표·작은 카드·pre만 */
    .cf-nr-chunk .cf-df .host,.cf-nr-chunk .cf-df details,.cf-nr-chunk .cf-df .arch-full,
    .cf-nr-chunk .cf-df .det,.cf-nr-chunk .cf-df .note,.cf-nr-chunk .cf-df .snap,
    .cf-nr-chunk .cfdev-mini .box{background:none!important;border:none!important;box-shadow:none!important;
      border-radius:0!important;padding:0!important;margin:0 0 14px!important;max-height:none!important;overflow:visible!important;}
    .cf-nr-chunk .cf-df pre,.cf-nr-chunk .cfdev-mini pre{margin:8px 0 14px!important;padding:10px 12px!important;
      background:#f5f5f5!important;color:#1b5e20!important;border:1px solid #e0e0e0!important;border-radius:8px!important;
      white-space:pre-wrap;word-break:break-all;}
    /* NR #!/4 순서도 카드(PC·Pi·UNO·SQLite…) 동일 크기 */
    .cf-nr-chunk .cf-df .row{display:flex!important;flex-wrap:wrap!important;gap:12px!important;
      justify-content:center!important;margin:6px 0 14px!important;align-items:stretch!important;}
    .cf-nr-chunk .cf-df .card{flex:1!important;min-width:136px!important;max-width:210px!important;
      text-align:center!important;padding:14px 10px!important;border-radius:16px!important;
      background:#fafafa!important;border:1px solid #e0e0e0!important;box-shadow:none!important;}
    .cf-nr-chunk .cf-df .ic svg{width:64px!important;height:64px!important;display:block!important;margin:0 auto 8px!important;}
    .cf-nr-chunk .cf-df .ar{align-self:center!important;font-size:1.3rem!important;color:#78909c!important;padding:0 2px!important;}
    .cf-nr-chunk .cf-df .tag{font-size:0.85rem!important;padding:4px 10px!important;line-height:1.45!important;
      color:#4e342e!important;background:#fff3e0!important;border:1px solid #ffcc80!important;border-radius:4px!important;}
    /* 본문 폰트 통일 */
    .cf-nr-chunk,.cf-nr-chunk p,.cf-nr-chunk li,.cf-nr-chunk ul,.cf-nr-chunk ol,
    .cf-nr-chunk .hb,.cf-nr-chunk .det,.cf-nr-chunk .lead,.cf-nr-chunk .cf-doc-lead,
    .cf-nr-chunk .cfdev-mini,.cf-nr-chunk .cfdev-mini p,.cf-nr-chunk .cfdev-mini li,
    .cf-nr-chunk .cf-df .s,.cf-nr-chunk .cf-df .sub,.cf-nr-chunk .cf-df .lab,.cf-nr-chunk .cf-df .hint,
    .cf-nr-chunk .cf-df .hb,.cf-nr-chunk .arch-full p,.cf-nr-chunk .note,.cf-nr-chunk pre{
      font-size:14px!important;line-height:1.6!important;}
    .cf-nr-chunk .cf-doc-h,.cf-nr-chunk h4{font-size:16px!important;}
    .cf-nr-chunk .cf-df .t{font-size:16px!important;}
    .cf-nr-chunk .cf-df .cap{font-size:11px!important;}
    .cf-nr-chunk table.grid,.cf-nr-chunk table,.cf-nr-chunk .cf-ent table{
      border:1px solid #ccc!important;border-collapse:collapse;}
    .cf-nr-chunk table th{background:#f5f5f5!important;color:#111!important;
      border:1px solid #e0e0e0!important;padding:6px 8px;}
    .cf-nr-chunk table td{background:#fff!important;color:#222!important;
      border:1px solid #e8e8e8!important;padding:6px 8px;}
    /* NR 다크 템플릿 → 흰 배경 가독 색 */
    .cf-nr-chunk .cf-df,.cf-nr-chunk .cf-df *{color:#222;}
    .cf-nr-chunk .cf-df .t,.cf-nr-chunk .cf-df .ht,.cf-nr-chunk .cfdev-mini h4{color:#2e7d32!important;}
    .cf-nr-chunk .cf-df .sub,.cf-nr-chunk .cf-df .s,.cf-nr-chunk .cf-df .lab,.cf-nr-chunk .cf-df .hint,
    .cf-nr-chunk .cf-df .hb,.cf-nr-chunk .cf-df .det,.cf-nr-chunk .cf-df li,.cf-nr-chunk .cfdev-mini,
    .cf-nr-chunk .cfdev-mini p,.cf-nr-chunk .cfdev-mini li{color:#333!important;}
    .cf-nr-chunk .cf-df .cap{color:#e65100!important;}
    .cf-nr-chunk .cf-df b,.cf-nr-chunk .cf-df strong,.cf-nr-chunk .cfdev-mini b,.cf-nr-chunk .cfdev-mini strong{color:#111!important;}
    .cf-nr-chunk .cf-df code,.cf-nr-chunk .cfdev-mini code{color:#c62828!important;background:#f5f5f5!important;}
    .cf-nr-chunk .cf-df a,.cf-nr-chunk .cfdev-mini a{color:#006064!important;}
    .cf-nr-chunk .cf-df .arch-full h6,.cf-nr-chunk .cf-df .host h5{color:#1565c0!important;}
    .cf-nr-chunk .cf-dev-hw-panel,.cf-nr-chunk .cf-dev-hw-panel p,.cf-nr-chunk .cf-dev-hw-panel td,
    .cf-nr-chunk .cf-dev-hw-panel th{color:#333!important;}
    .cf-nr-chunk .cf-dev-hw-panel a{color:#006064!important;}
    .cf-nr-chunk .lead,.cf-nr-chunk .cf-doc-lead{color:#444!important;}
    /* 숨겨졌던 제목·요약 복구 */
    .cf-dev-page .cf-df .host h5,.cf-dev-page .cf-df details summary{display:block!important;}
    .cf-dev-page.cf-ent h4,.cf-dev-page .cf-ent h4{display:block!important;}
    """
    if layout_css:
        page_css += "\n    /* NR #!/4 레이아웃 */\n    " + layout_css.replace("\n", "\n    ")
    if embedded_css:
        page_css += "\n    /* NR 템플릿 내장 */\n    " + "\n    ".join(
            c.replace("\n", "\n    ") for c in embedded_css
        )
    page_css += """
    /* cf-pu · cf-df-paths · hw-panel — 흰 배경 가독 (템플릿 다크색 덮어씀) */
    .cf-nr-chunk .cf-df-paths,.cf-nr-chunk .cf-df-paths p,.cf-nr-chunk .cf-df-paths li,.cf-nr-chunk .cf-df-paths ul{color:#333!important;}
    .cf-nr-chunk .cf-df-paths h3{color:#2e7d32!important;}
    .cf-nr-chunk .cf-df-paths strong{color:#111!important;}
    .cf-nr-chunk .cf-df-paths code{color:#c62828!important;background:#f5f5f5!important;}
    .cf-nr-chunk .cf-df-paths .pi{color:#006064!important;}
    .cf-nr-chunk .cf-df-paths a{color:#006064!important;}
    .cf-nr-chunk .cf-pu,.cf-nr-chunk .cf-pu p,.cf-nr-chunk .cf-pu li,.cf-nr-chunk .cf-pu ul,
    .cf-nr-chunk .cf-pu span,.cf-nr-chunk .cf-pu .cap,.cf-nr-chunk .cf-pu .note{color:#333!important;}
    .cf-nr-chunk .cf-pu h3{color:#2e7d32!important;}
    .cf-nr-chunk .cf-pu h4{color:#1565c0!important;}
    .cf-nr-chunk .cf-pu h5{color:#555!important;}
    .cf-nr-chunk .cf-pu a{color:#006064!important;}
    .cf-nr-chunk .cf-pu code{color:#c62828!important;background:#f5f5f5!important;}
    .cf-nr-chunk .cf-pu .snap{background:#f5f5f5!important;color:#1b5e20!important;border:1px solid #e0e0e0!important;padding:10px 12px!important;white-space:pre!important;}
    .cf-nr-chunk .cf-pu .dial{background:#f9f9f9!important;border:1px solid #e0e0e0!important;color:#333!important;}
    .cf-nr-chunk .cf-pu .dial strong{color:#111!important;}
    .cf-nr-chunk .cf-pu table th{background:#f5f5f5!important;color:#111!important;border-color:#e0e0e0!important;}
    .cf-nr-chunk .cf-pu table td{background:#fff!important;color:#222!important;border-color:#e8e8e8!important;}
    .cf-nr-chunk .cf-pu .note{background:#f9fbe7!important;border-left:3px solid #5c6bc0!important;color:#444!important;padding:8px 12px!important;}
    .cf-nr-chunk .cf-dev-hw-panel,.cf-nr-chunk .cf-dev-hw-panel p,.cf-nr-chunk .cf-dev-hw-panel li,
    .cf-nr-chunk .cf-dev-hw-panel td,.cf-nr-chunk .cf-dev-hw-panel th{color:#333!important;}
    .cf-nr-chunk .cf-dev-hw-panel p[style*="color:#aed581"]{color:#2e7d32!important;font-weight:700!important;}
    .cf-nr-chunk .cf-dev-hw-panel p[style*="color:#90caf9"]{color:#1565c0!important;font-weight:700!important;}
    .cf-nr-chunk .cf-dev-hw-panel code{color:#c62828!important;background:#f5f5f5!important;}
    .cf-nr-chunk .cf-dev-hw-panel a{color:#006064!important;}
    .cf-nr-chunk .cf-dev-hw-panel table th{background:#f5f5f5!important;}
    .cf-nr-chunk .cf-dev-hw-panel table td{background:#fff!important;}
    .cf-nr-chunk .cf-dev-arch,.cf-nr-chunk .cf-dev-arch p,.cf-nr-chunk .cf-dev-arch li{color:#333!important;}
    .cf-nr-chunk .cf-dev-arch h3{color:#1565c0!important;}
    /* 펼치기/접기 */
    .cf-dev-fold{border:1px solid #e0e0e0;border-radius:8px;margin:14px 0;background:#fafafa;overflow:visible;}
    .cf-dev-fold summary{cursor:pointer;padding:10px 14px;font-size:14px!important;font-weight:700;
      color:#1565c0!important;background:#f5f5f5;list-style:revert;}
    .cf-dev-fold[open]>summary{border-bottom:1px solid #e0e0e0;}
    .cf-dev-fold-body{padding:10px 14px 14px;color:#333!important;}
    .cf-boot-inline h1{font-size:16px!important;color:#111!important;margin:0 0 10px;}
    .cf-boot-inline h2{font-size:14px!important;color:#333!important;border-bottom:1px solid #e0e0e0;padding-bottom:4px;}
    .cf-boot-inline table th{background:#f5f5f5!important;color:#111!important;}
    .cf-boot-inline table td{background:#fff!important;color:#222!important;}
    .cf-boot-inline .note{color:#444!important;}
    /* layout_css 보정 — 흰 배경·숨김 해제 */
    .cf-dev-page .cf-df .host h5,.cf-dev-page .cf-df details summary{display:block!important;}
    .cf-dev-page.cf-ent h4,.cf-dev-page .cf-ent h4{display:block!important;}
    html,body,.cf-settings-app,.cf-settings-shell,.cf-nr-chunk,.cf-dev-page{background:#fff!important;color:#222!important;}
    /* farm-ui SPA iframe embed */
    body.cf-embed .cf-mhdr,body.cf-embed #cf-dev-drawer,body.cf-embed #cf-dev-drawer-back{display:none!important;}
    body.cf-embed .cf-settings-app{max-width:none;margin:0;padding:0;}
    body.cf-embed .cf-settings-shell{padding:8px 12px 20px;}
    /* 흰 배경 — 인라인·템플릿 다크색 일괄 보정 (최종 우선) */
    .cf-settings-shell .cf-df-paths,.cf-settings-shell .cf-df-paths p,.cf-settings-shell .cf-df-paths li,.cf-settings-shell .cf-df-paths ul{color:#333!important;}
    .cf-settings-shell .cf-df-paths h3,.cf-settings-shell .cf-df-paths strong{color:#2e7d32!important;}
    .cf-settings-shell .cf-df-paths code{color:#c62828!important;background:#f5f5f5!important;}
    .cf-settings-shell .cf-df-paths .pi{color:#006064!important;}
    .cf-settings-shell .cf-pu,.cf-settings-shell .cf-pu p,.cf-settings-shell .cf-pu li,.cf-settings-shell .cf-pu ul,.cf-settings-shell .cf-pu span,.cf-settings-shell .cf-pu .cap,.cf-settings-shell .cf-pu .note,.cf-settings-shell .cf-pu .dial,.cf-settings-shell .cf-pu .dial strong{color:#333!important;}
    .cf-settings-shell .cf-pu h3{color:#2e7d32!important;}
    .cf-settings-shell .cf-pu h4,.cf-settings-shell .cf-pu h5{color:#1565c0!important;}
    .cf-settings-shell .cf-pu a,.cf-settings-shell .cf-df-paths a{color:#006064!important;}
    .cf-settings-shell .cf-pu code{color:#c62828!important;background:#f5f5f5!important;}
    .cf-settings-shell .cf-pu .snap{color:#1b5e20!important;background:#f5f5f5!important;border:1px solid #e0e0e0!important;}
    .cf-settings-shell .cf-dev-hw-panel,.cf-settings-shell .cf-dev-hw-panel p,.cf-settings-shell .cf-dev-hw-panel li,.cf-settings-shell .cf-dev-hw-panel td,.cf-settings-shell .cf-dev-hw-panel th{color:#333!important;}
    .cf-settings-shell .cf-dev-hw-panel a{color:#006064!important;}
    .cf-settings-shell .cf-dev-hw-panel code{color:#c62828!important;background:#f5f5f5!important;}
    .cf-settings-shell .cf-dev-hw-panel p[style*="font-weight:700"]{color:#2e7d32!important;}
    .cf-settings-shell [style*="color:#ececec"],.cf-settings-shell [style*="color:#cfd8dc"],.cf-settings-shell [style*="color:#e8f0fe"],.cf-settings-shell [style*="color:#e6edf7"],.cf-settings-shell [style*="color:#b0bec5"],.cf-settings-shell [style*="color:#aed581"],.cf-settings-shell [style*="color:#90caf9"],.cf-settings-shell [style*="color:#80deea"]{color:#333!important;}
    .cf-dev-fold{border:1px solid #ddd!important;border-radius:8px!important;margin:12px 0!important;background:#fafafa!important;}
    .cf-dev-fold summary{display:list-item!important;cursor:pointer!important;color:#1565c0!important;visibility:visible!important;font-weight:700!important;padding:10px 14px!important;background:#f5f5f5!important;}
    .cf-dev-fold[open]>summary{border-bottom:1px solid #e0e0e0!important;margin-bottom:8px!important;}
    .cf-dev-fold-body{color:#333!important;padding:8px 14px 14px!important;}
    /* SPA devstatus 최종 보정 */
    .cf-df-paths,.cf-df-paths p,.cf-df-paths li,.cf-df-paths ul,.cf-df-paths span{color:#333!important;}
    .cf-df-paths h3,.cf-df-paths strong{color:#2e7d32!important;}
    .cf-df-paths code{color:#c62828!important;background:#f5f5f5!important;}
    .cf-df-paths .pi,.cf-df-paths a{color:#006064!important;}
    .cf-pu,.cf-pu p,.cf-pu li,.cf-pu ul,.cf-pu span,.cf-pu .cap,.cf-pu .note,.cf-pu .dial,.cf-pu .dial strong{color:#333!important;}
    .cf-pu h3{color:#2e7d32!important;}
    .cf-pu h4,.cf-pu h5{color:#1565c0!important;}
    .cf-pu a{color:#006064!important;}
    .cf-pu code{color:#c62828!important;background:#f5f5f5!important;}
    .cf-pu .snap{color:#1b5e20!important;background:#f5f5f5!important;border:1px solid #e0e0e0!important;}
    .cf-pu table th{background:#f5f5f5!important;color:#111!important;}
    .cf-pu table td{background:#fff!important;color:#222!important;}
    .cf-dev-hw-panel,.cf-dev-hw-panel p,.cf-dev-hw-panel li,.cf-dev-hw-panel td,.cf-dev-hw-panel th{color:#333!important;}
    .cf-dev-hw-panel a{color:#006064!important;}
    .cf-dev-hw-panel code,.cf-dev-hw-panel code[style]{color:#c62828!important;background:#f5f5f5!important;}
    .cf-dev-hw-panel table,.cf-dev-hw-panel table[style]{color:#222!important;}
    .cf-dev-hw-panel table th,.cf-dev-hw-panel table th[style]{background:#f5f5f5!important;color:#111!important;border-color:#e0e0e0!important;}
    .cf-dev-hw-panel table td,.cf-dev-hw-panel table td[style]{background:#fff!important;color:#222!important;border-color:#e8e8e8!important;}
    .cf-dev-hw-panel [style*="color:#ececec"],.cf-dev-hw-panel [style*="color:#aed581"],.cf-dev-hw-panel [style*="color:#90caf9"],.cf-dev-hw-panel [style*="color:#ffcc80"]{color:#333!important;}
    .cf-dev-hw-panel p[style*="aed581"]{color:#2e7d32!important;font-weight:700!important;}
    .cf-dev-hw-panel p[style*="90caf9"]{color:#1565c0!important;font-weight:700!important;}
    details.cf-dev-fold>summary{display:list-item!important;visibility:visible!important;opacity:1!important;color:#1565c0!important;cursor:pointer!important;}
    """

    resize_js = """
(function(){var e=/[?&]embed=1(?:&|$)/.test(location.search)||window.self!==window.top;
if(e)document.body.classList.add('cf-embed');})();
window.addEventListener('message',function(ev){
  var d=ev.data;if(!d||d.type!=='cf-devflow-scroll'||!d.id)return;
  document.getElementById(d.id)?.scrollIntoView({behavior:'smooth',block:'start'});
  cfDevResize();
});
function cfDevResize(){try{var h=document.documentElement.scrollHeight;
parent.postMessage({type:'cf-devflow-iframe-resize',height:h},'*');}catch(e){}}
window.addEventListener('load',function(){cfDevResize();setTimeout(cfDevResize,400);
  document.querySelectorAll('details.cf-dev-fold').forEach(function(d){d.addEventListener('toggle',cfDevResize);});
});
window.addEventListener('resize',cfDevResize);
setInterval(cfDevResize,2500);
document.querySelectorAll('[data-cf-scroll]').forEach(function(btn){
  btn.addEventListener('click',function(){
    var id=btn.getAttribute('data-cf-scroll');
    document.getElementById(id)?.scrollIntoView({behavior:'smooth',block:'start'});
    var d=document.getElementById('cf-dev-drawer');var b=document.getElementById('cf-dev-drawer-back');
    if(d)d.classList.remove('open');if(b)b.style.display='none';
    cfDevResize();
  });
});
var burger=document.getElementById('cf-dev-burger');
var back=document.getElementById('cf-dev-drawer-back');
if(burger){burger.addEventListener('click',function(){
  var d=document.getElementById('cf-dev-drawer');var open=d&&d.classList.toggle('open');
  if(back)back.style.display=open?'block':'none';
});}
if(back){back.addEventListener('click',function(){
  document.getElementById('cf-dev-drawer')?.classList.remove('open');back.style.display='none';
});}
cfDevResize();
"""

    nav_js = """
var O=location.origin||'';
document.querySelectorAll('[data-cf-href]').forEach(function(el){
  var role=el.getAttribute('data-cf-href');
  if(role==='settings')el.setAttribute('href',O+'/farm/ui/#/');
  if(role==='admin')el.setAttribute('href',O+'/farm/ui/#/admin');
  el.addEventListener('click',function(e){
    e.preventDefault();
    var u=el.getAttribute('href');
    try{(window.top||window).location.replace(u);}catch(err){location.replace(u);}
  });
});
"""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>CronusFarm 개발현황</title>
  <style>{page_css}</style>
</head>
<body>
<div id="cf-dev-drawer-back" class="cf-drawer-back" style="display:none"></div>
<nav id="cf-dev-drawer" class="cf-drawer" aria-label="개발현황 메뉴">
  <div class="cf-drawer-hd">메뉴</div>
  <a class="cf-drawer-item cf-drawer-route" data-cf-href="settings" href="#">CronusFarm 설정</a>
  <a class="cf-drawer-item cf-drawer-route" data-cf-href="admin" href="#">CronusFarm 관리</a>
  <p class="cf-drawer-sec-title">개발현황</p>
{menu_li}
</nav>
<header class="cf-mhdr">
  <button type="button" class="cf-mhdr-burger" id="cf-dev-burger" aria-label="메뉴 열기"><span></span><span></span><span></span></button>
  <h1 class="cf-mhdr-title">CronusFarm 개발현황</h1>
  <nav class="cf-mhdr-nav">
    <a class="cf-mhdr-link" data-cf-href="settings" href="#">설정</a>
    <a class="cf-mhdr-link" data-cf-href="admin" href="#">관리</a>
  </nav>
</header>
<div class="cf-settings-app">
  <div class="cf-settings-shell">
    <p class="cf-dev-lead"><strong>개발 → 배포 → 서비스</strong> · PC 저장소 정본 → merge → Pi apply. 아래 섹션은 기존 Node-RED 문서·링크(mega.html, GitHub, Grafana 등)를 그대로 포함합니다.</p>
{"".join(chunks)}
  </div>
</div>
<script>{nav_js}</script>
<script>{resize_js}</script>
</body>
</html>
"""


def _patch_devflow_nodes(raw: list) -> list:
    by = {n["id"]: n for n in raw if isinstance(n, dict) and n.get("id")}
    html = _build_devflow_html(by)
    HTML_OUT.write_text(html, encoding="utf-8")

    iframe_node = {
        "id": TPL_IFRAME,
        "type": "ui_template",
        "z": "tab_cronus_devflow",
        "group": GRP_MAIN,
        "name": "개발현황(설정형 iframe)",
        "order": 1,
        "width": "12",
        "height": "48",
        "format": IFRAME_FMT,
        "storeOutMessages": False,
        "fwdInMessages": False,
        "resendOnRefresh": True,
        "templateScope": "local",
        "x": 360,
        "y": 120,
        "wires": [[]],
    }
    layout_node = {
        "id": TPL_LAYOUT,
        "type": "ui_template",
        "z": "tab_cronus_devflow",
        "group": GRP_MAIN,
        "name": "개발현황: 레이아웃(CSS)",
        "order": 0,
        "width": "0",
        "height": "0",
        "format": LAYOUT_FMT,
        "storeOutMessages": False,
        "fwdInMessages": False,
        "resendOnRefresh": True,
        "templateScope": "local",
        "x": 200,
        "y": 80,
        "wires": [[]],
    }

    out: list = []
    seen_iframe = False
    seen_layout = False
    for n in raw:
        if not isinstance(n, dict):
            out.append(n)
            continue
        nid = n.get("id")
        if nid == TPL_IFRAME:
            out.append(iframe_node)
            seen_iframe = True
            continue
        if nid == TPL_LAYOUT:
            out.append(layout_node)
            seen_layout = True
            continue
        if n.get("type") == "ui_template" and nid in DEVFLOW_HIDE_TPL_IDS and nid not in KEEP_TPL_IDS:
            n = dict(n)
            n["format"] = HIDDEN_STUB
            n["height"] = 0
            n["width"] = 0
            n["order"] = 90
        if n.get("id") == GRP_MAIN:
            n = dict(n)
            n["name"] = "개발 → 배포 → 서비스"
            n["disp"] = True
            n["order"] = 1
            n["className"] = MONITOR_GROUP_CLASS
        if n.get("id") == "ui_grp_devflow_entity":
            n = dict(n)
            n["disp"] = False
            n["order"] = 99
        if n.get("id") == TAB_DEV.replace("tab_", "ui_tab_") or n.get("id") == "ui_tab_devflow":
            n = dict(n)
            n["name"] = "CronusFarm 개발현황"
        out.append(n)

    if not seen_iframe:
        out.append(iframe_node)
    if not seen_layout:
        out.append(layout_node)

    return out


def _patch_dashboard_devflow_tab(raw: list) -> list:
    by = {n["id"]: n for n in raw if isinstance(n, dict) and n.get("id")}
    for nid in ("ui_tab_devflow", "ui_grp_devflow"):
        if nid in by:
            src = by[nid]
            for n in raw:
                if isinstance(n, dict) and n.get("id") == nid:
                    if nid == "ui_tab_devflow":
                        n["name"] = "CronusFarm 개발현황"
                    if nid == "ui_grp_devflow":
                        n["name"] = "개발 → 배포 → 서비스"
                        n["className"] = MONITOR_GROUP_CLASS
    return raw


def _apply_file(path: Path) -> None:
    if not path.is_file():
        return
    raw: list = json.loads(path.read_text(encoding="utf-8-sig"))
    if path == DEVFLOW:
        raw = _patch_devflow_nodes(raw)
    elif path == DASH:
        raw = _patch_dashboard_devflow_tab(raw)
    else:
        by = {n["id"]: n for n in raw if isinstance(n, dict) and n.get("id")}
        if TPL_IFRAME in by or "ui_tpl_devflow_diagram" in by:
            dev_nodes = json.loads(DEVFLOW.read_text(encoding="utf-8-sig"))
            dev_by = {n["id"]: n for n in dev_nodes if isinstance(n, dict) and n.get("id")}
            for n in raw:
                if not isinstance(n, dict):
                    continue
                tid = n.get("id")
                if tid in dev_by and n.get("type") == "ui_template":
                    if tid in KEEP_TPL_IDS:
                        n["format"] = dev_by[tid]["format"]
                    elif tid.startswith(("ui_tpl_devflow", "ui_tpl_cf_comm", "cf_tpl_dev")):
                        n["format"] = HIDDEN_STUB
    path.write_text(
        json.dumps(raw, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    if not DEVFLOW.is_file():
        print(f"ERROR: {DEVFLOW} 없음", file=sys.stderr)
        return 1
    raw = json.loads(DEVFLOW.read_text(encoding="utf-8-sig"))
    patched = _patch_devflow_nodes(raw)
    DEVFLOW.write_text(
        json.dumps(patched, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    for p in FLOW_TARGETS[1:]:
        _apply_file(p)
    print(f"OK {HTML_OUT.name} ({HTML_OUT.stat().st_size} bytes)")
    print(f"OK {DEVFLOW.name} → iframe + hidden stubs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
