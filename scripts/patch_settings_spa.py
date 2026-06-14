# -*- coding: utf-8 -*-
"""설정: D1 좌측 탭 목록에「CronusFarm 설정」ui_tab(빈 탭) — 클릭 시 SPA로 즉시 이동(iframe·중간 페이지 없음)."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
INDEX = ROOT / "nodered" / "dashboard" / "index.html"
FLOW_FILES = [
    DASH,
    ROOT / "nodered" / "merged-deploy.json",
    ROOT / "nodered" / "CronusFarm_NodeRED_flow.json",
]

SPA_ENTRY = "/farm/ui/#/"
SETTINGS_TAB_ID = "ui_tab_settings"
SETTINGS_TAB_NODE = {
    "id": SETTINGS_TAB_ID,
    "type": "ui_tab",
    "name": "CronusFarm 설정",
    "icon": "settings",
    "order": 2,
    "disabled": False,
    "hidden": False,
}
# ui_group 없는 ui_tab은 md-sidenav 목록에 안 나옴 → 최소 그룹·숨김 템플릿만 둠
SETTINGS_GROUP_ID = "ui_grp_settings_spa"
SETTINGS_TPL_ID = "ui_tpl_settings_spa"
SETTINGS_GROUP_NODE = {
    "id": SETTINGS_GROUP_ID,
    "type": "ui_group",
    "name": "설정(SPA)",
    "tab": SETTINGS_TAB_ID,
    "order": 1,
    "disp": False,
    "width": "12",
    "collapse": True,
}
SETTINGS_TPL_FORMAT = (
    '<div data-cf-settings-spa="1" style="display:none" aria-hidden="true"></div>'
    "<script>(function(){var u=(location.origin||'')+'/farm/ui/#/';"
    "try{(window.top||window).location.replace(u);}catch(e){location.replace(u);}"
    "})();</script>"
)

# 설정 탭(#!/1) — Angular 전환 시에도 SPA로 즉시 이동 (중간 페이지 방지)
INDEX_REDIRECT_JS = r"""
    <script type="text/javascript">
      (function () {
        var SPA = (location.origin || '') + '/farm/ui/#/';
        function isSettingsHash() {
          var h = (location.hash || '').replace(/^#/, '');
          return /^!\/1(?:[?#/]|$)/.test(h);
        }
        function go() {
          if (!isSettingsHash()) return false;
          location.replace(SPA);
          return true;
        }
        go();
        window.addEventListener('hashchange', go);
        var n = 0;
        var iv = setInterval(function () {
          if (go() || ++n > 100) clearInterval(iv);
        }, 100);
      })();
    </script>
"""

MENUBAR_CSS_MARK = "/* cf-d1-menubar */"
MENUBAR_CSS = (
    MENUBAR_CSS_MARK
    + """
#nr-dashboard{--cf-border2:rgba(45,255,122,.16);--cf-accent:#2dff7a;--cf-accent2:#00e5ff;--cf-accent3:#ffb830;--cf-text:#c8e6c9;--cf-text2:#6b9c73;--cf-muted:#6b9c73;}
body.nr-dashboard-theme md-toolbar .md-toolbar-tools:has(#cf-d1-menubar) md-tabs{display:none!important;}
body.nr-dashboard-theme md-toolbar .md-toolbar-tools:has(#cf-d1-menubar){
  display:flex!important;align-items:center!important;flex-wrap:nowrap!important;gap:8px!important;}
#cf-d1-menubar.cf-mhdr{display:flex;align-items:center;gap:12px;flex:1 1 auto;min-width:0;margin:0;padding:4px 8px 4px 0;border-bottom:none;}
#cf-d1-menubar .cf-mhdr-burger{display:flex;flex-direction:column;justify-content:center;gap:5px;width:42px;height:42px;padding:0;border:1px solid var(--cf-border2);border-radius:10px;background:rgba(0,0,0,.28);cursor:pointer;flex-shrink:0;}
#cf-d1-menubar .cf-mhdr-burger span{display:block;width:18px;height:2px;margin:0 auto;background:var(--cf-accent);border-radius:1px;}
#cf-d1-menubar .cf-mhdr-title{margin:0;flex:1 1 auto;min-width:0;font-size:1.05rem;font-weight:900;color:var(--cf-accent3);letter-spacing:.02em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
#cf-d1-menubar .cf-mhdr-nav{display:flex;gap:8px;margin-left:auto;flex-shrink:0;}
#cf-d1-menubar .cf-mhdr-link{font-size:12px;font-weight:800;color:var(--cf-accent2);text-decoration:none;padding:6px 10px;border-radius:8px;border:1px solid var(--cf-border2);white-space:nowrap;}
#cf-d1-menubar .cf-mhdr-link:hover{color:#e6edf7;border-color:rgba(45,255,122,.45);background:rgba(45,255,122,.1);}
#cf-d1-menubar #cf-d1-link-settings{color:var(--cf-accent3);border-color:rgba(255,184,48,.45);font-weight:900;}
#cf-d1-menubar .cf-mhdr-link.on{color:#e6edf7;border-color:rgba(45,255,122,.35);background:rgba(45,255,122,.1);}
body.nr-dashboard-theme md-toolbar .md-toolbar-tools:has(#cf-d1-menubar){overflow-x:auto!important;overflow-y:visible!important;}
.cf-d1-drawer-back{position:fixed;inset:0;z-index:200;background:rgba(0,0,0,.45);}
.cf-d1-drawer{position:fixed;top:0;left:0;bottom:0;z-index:210;width:min(280px,86vw);padding:14px 12px 20px;background:rgba(4,13,7,.97);border-right:1px solid var(--cf-border2);box-shadow:8px 0 32px rgba(0,0,0,.45);transform:translateX(-105%);transition:transform .22s ease;}
.cf-d1-drawer.open{transform:translateX(0);}
.cf-d1-drawer-hd{margin:0 0 12px;padding-bottom:8px;border-bottom:1px solid var(--cf-border2);font-size:11px;font-weight:800;color:var(--cf-text2);letter-spacing:.12em;text-transform:uppercase;}
.cf-d1-drawer-item{display:block;width:100%;margin:0 0 6px;padding:11px 12px;border:1px solid transparent;border-radius:10px;background:transparent;color:var(--cf-text);font-size:13px;font-weight:800;text-align:left;cursor:pointer;text-decoration:none;box-sizing:border-box;}
.cf-d1-drawer-item:hover{background:rgba(45,255,122,.08);border-color:rgba(45,255,122,.2);}
.cf-d1-drawer-sec{margin:14px 0 6px;font-size:11px;font-weight:800;color:var(--cf-text2);letter-spacing:.08em;}
"""
)

INDEX_MENUBAR_JS = r"""
    <script type="text/javascript">
      (function () {
        var ORIGIN = location.origin || '';
        var SPA = ORIGIN + '/farm/ui/#/';
        var SPA_ADMIN = ORIGIN + '/farm/ui/#/admin';
        function isSettingsLabel(label) {
          return /CronusFarm\s*설정/.test(label || '');
        }
        function redirectSettingsTab() {
          var h0 = (location.hash || '').replace(/^#/, '');
          if (/^!\/1(?:[?#/]|$)/.test(h0)) { location.replace(SPA); return true; }
          return false;
        }
        var drawerOpen = false;
        function goHref(href, ev) {
          if (ev) { ev.preventDefault(); ev.stopPropagation(); }
          closeDrawer();
          try { (window.top || window).location.replace(href); }
          catch (e) { location.replace(href); }
        }
        function findTools() {
          var list = document.querySelectorAll('md-toolbar .md-toolbar-tools');
          for (var i = 0; i < list.length; i++) {
            if (list[i].querySelector('md-tabs')) return list[i];
          }
          return document.querySelector('md-toolbar .md-toolbar-tools');
        }
        function nrTabs() {
          var root = document.querySelector('md-tabs');
          if (!root) return [];
          return Array.prototype.slice.call(root.querySelectorAll('md-tab'));
        }
        function activeTabTitle() {
          var tabs = nrTabs();
          for (var i = 0; i < tabs.length; i++) {
            if (tabs[i].classList.contains('md-active')) return (tabs[i].textContent || '').trim();
          }
          return (tabs[0] && tabs[0].textContent || 'CronusFarm 모니터').trim();
        }
        function clickNrTab(ix) {
          var tabs = nrTabs();
          if (!tabs[ix]) return;
          var label = (tabs[ix].textContent || '').trim();
          if (isSettingsLabel(label)) { goHref(SPA); return; }
          tabs[ix].click();
          var t = document.getElementById('cf-d1-title');
          if (t) t.textContent = label || 'CronusFarm';
        }
        function hijackSettingsSidenav() {
          var items = document.querySelectorAll('md-sidenav md-list-item');
          for (var i = 0; i < items.length; i++) {
            if (!isSettingsLabel((items[i].textContent || '').trim())) continue;
            if (items[i].__cfSpaNav) continue;
            items[i].__cfSpaNav = 1;
            items[i].addEventListener('click', function (e) {
              goHref(SPA, e);
            }, true);
          }
        }
        function closeDrawer() {
          drawerOpen = false;
          var d = document.getElementById('cf-d1-drawer');
          var b = document.getElementById('cf-d1-drawer-back');
          if (d) d.classList.remove('open');
          if (b) b.style.display = 'none';
        }
        function openDrawer() {
          drawerOpen = true;
          rebuildDrawerTabs();
          var d = document.getElementById('cf-d1-drawer');
          var b = document.getElementById('cf-d1-drawer-back');
          if (d) d.classList.add('open');
          if (b) b.style.display = 'block';
        }
        function rebuildDrawerTabs() {
          var host = document.getElementById('cf-d1-drawer-tabs');
          if (!host) return;
          host.innerHTML = '';
          var tabs = nrTabs();
          for (var i = 0; i < tabs.length; i++) {
            (function (ix, label) {
              var btn = document.createElement('button');
              btn.type = 'button';
              btn.className = 'cf-d1-drawer-item';
              btn.textContent = label;
              btn.addEventListener('click', function () {
                if (isSettingsLabel(label)) goHref(SPA);
                else clickNrTab(ix);
                closeDrawer();
              });
              host.appendChild(btn);
            })(i, (tabs[i].textContent || '').trim());
          }
        }
        function ensureDrawer() {
          if (document.getElementById('cf-d1-drawer')) return;
          var back = document.createElement('div');
          back.id = 'cf-d1-drawer-back';
          back.className = 'cf-d1-drawer-back';
          back.style.display = 'none';
          back.addEventListener('click', closeDrawer);
          var nav = document.createElement('nav');
          nav.id = 'cf-d1-drawer';
          nav.className = 'cf-d1-drawer';
          nav.setAttribute('aria-label', '메뉴');
          nav.innerHTML =
            '<div class="cf-d1-drawer-hd">메뉴</div>' +
            '<a class="cf-d1-drawer-item" href="' + SPA + '">CronusFarm 설정</a>' +
            '<a class="cf-d1-drawer-item" href="' + SPA_ADMIN + '">CronusFarm 관리</a>' +
            '<p class="cf-d1-drawer-sec">대시보드</p>' +
            '<div id="cf-d1-drawer-tabs"></div>';
          nav.querySelector('a[href="' + SPA + '"]').addEventListener('click', function (e) { goHref(SPA, e); });
          nav.querySelector('a[href="' + SPA_ADMIN + '"]').addEventListener('click', function (e) { goHref(SPA_ADMIN, e); });
          document.body.appendChild(back);
          document.body.appendChild(nav);
        }
        function buildMenubar() {
          var bar = document.createElement('div');
          bar.id = 'cf-d1-menubar';
          bar.className = 'cf-mhdr';
          bar.innerHTML =
            '<button type="button" class="cf-mhdr-burger" aria-label="메뉴 열기">' +
            '<span></span><span></span><span></span></button>' +
            '<h1 class="cf-mhdr-title" id="cf-d1-title">CronusFarm 모니터</h1>' +
            '<nav class="cf-mhdr-nav" aria-label="상단 메뉴">' +
            '<a class="cf-mhdr-link" id="cf-d1-link-settings" href="' + SPA + '">CronusFarm 설정</a>' +
            '<a class="cf-mhdr-link" id="cf-d1-link-admin" href="' + SPA_ADMIN + '">CronusFarm 관리</a>' +
            '</nav>';
          bar.querySelector('.cf-mhdr-burger').addEventListener('click', function () {
            if (drawerOpen) closeDrawer(); else openDrawer();
          });
          bar.querySelector('#cf-d1-link-settings').addEventListener('click', function (e) { goHref(SPA, e); });
          bar.querySelector('#cf-d1-link-admin').addEventListener('click', function (e) { goHref(SPA_ADMIN, e); });
          return bar;
        }
        function ensureMenubar() {
          var tools = findTools();
          if (!tools) return false;
          ensureDrawer();
          var bar = document.getElementById('cf-d1-menubar');
          if (bar && bar.parentElement === tools) return true;
          if (bar) bar.remove();
          bar = buildMenubar();
          tools.insertBefore(bar, tools.firstChild);
          var clock = document.getElementById('cf-monitor-tab-clock');
          if (clock && clock.parentElement !== tools) tools.appendChild(clock);
          return true;
        }
        function syncTitle() {
          var t = document.getElementById('cf-d1-title');
          if (t) t.textContent = activeTabTitle() || 'CronusFarm 모니터';
        }
        function boot() {
          redirectSettingsTab();
          hijackSettingsSidenav();
          if (!ensureMenubar()) return;
          syncTitle();
        }
        if (!window.__cfD1MenubarInit) {
          window.__cfD1MenubarInit = 1;
          document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeDrawer(); });
          window.addEventListener('hashchange', function () {
            if (redirectSettingsTab()) return;
            syncTitle();
          });
          document.addEventListener('DOMContentLoaded', boot);
          try {
            var obs = new MutationObserver(function () {
              if (!document.getElementById('cf-d1-menubar')) boot();
            });
            obs.observe(document.documentElement, { childList: true, subtree: true });
          } catch (e) { /* ignore */ }
          setInterval(boot, 3000);
        }
        boot();
        var n = 0;
        var iv = setInterval(function () {
          boot();
          if (++n > 120) clearInterval(iv);
        }, 200);
      })();
    </script>
"""

OLD_SETTINGS_JS_RE = re.compile(
    r"<script type=\"text/javascript\">\s*\(function \(\) \{[\s\S]*?"
    r"(?:__cfGoSettingsTab|__cfSettingsMenuLink|__cfD1Menubar|__cfD1MenubarInit|isSettingsHash)[\s\S]*?\}\)\(\);\s*</script>\s*",
    re.MULTILINE,
)
OLD_REDIRECT_JS_RE = re.compile(
    r"<script type=\"text/javascript\">\s*\(function \(\) \{\s*var SPA = \(location\.origin[\s\S]*?isSettingsHash[\s\S]*?\}\)\(\);\s*</script>\s*",
    re.MULTILINE,
)
OLD_MENUBAR_STYLE_RE = re.compile(
    r"<style>[\s\S]*?(?:cf-settings-menu-link|cf-d1-menubar)[\s\S]*?</style>\s*",
    re.MULTILINE,
)

SETTINGS_TAB_HIDE_CSS = (
    "body.nr-dashboard-theme md-content:has([data-cf-settings-spa]){"
    "min-height:0!important;padding:0!important;}"
    "body.nr-dashboard-theme md-content:has([data-cf-settings-spa]) .nr-dashboard-default,"
    "body.nr-dashboard-theme md-content:has([data-cf-settings-spa]) table{display:none!important;}"
)

DROP_GROUP_IDS = frozenset(
    {"ui_grp_settings_sched_ov", "ui_grp_settings_tools", "ui_grp_settings_beds"}
)
DROP_NODE_IDS = frozenset(
    {
        "ui_tpl_settings_arch",
        "ui_tpl_settings_beds_iframe",
        "ui_tpl_settings_sched_ov_iframe",
        "ui_tpl_settings_tools_iframe",
    }
)


def _flow_z(by: dict) -> str:
    for nid in ("ui_tpl_pi_nodered", "ui_tpl_css_cronus"):
        n = by.get(nid)
        if isinstance(n, dict) and n.get("z"):
            return str(n["z"])
    for n in by.values():
        if isinstance(n, dict) and n.get("type") == "ui_template" and n.get("z"):
            return str(n["z"])
    return "tab_cronus_dash"


def _ensure_settings_spa_shell(out: list, by: dict) -> None:
    """설정 탭이 사이드 메뉴에 보이도록 빈 그룹·템플릿을 보장한다."""
    grp = by.get(SETTINGS_GROUP_ID)
    if grp:
        grp["tab"] = SETTINGS_TAB_ID
        grp["disp"] = False
    else:
        out.append(dict(SETTINGS_GROUP_NODE))
        by[SETTINGS_GROUP_ID] = SETTINGS_GROUP_NODE

    tpl = by.get(SETTINGS_TPL_ID)
    if tpl:
        tpl["group"] = SETTINGS_GROUP_ID
        tpl["format"] = SETTINGS_TPL_FORMAT
        tpl["height"] = "0"
        tpl["width"] = "0"
    else:
        out.append(
            {
                "id": SETTINGS_TPL_ID,
                "type": "ui_template",
                "z": _flow_z(by),
                "group": SETTINGS_GROUP_ID,
                "name": "SPA(숨김)",
                "order": 1,
                "width": "0",
                "height": "0",
                "format": SETTINGS_TPL_FORMAT,
                "storeOutMessages": False,
                "fwdInMessages": False,
                "resendOnRefresh": False,
                "templateScope": "local",
                "wires": [[]],
            }
        )


def _patch_index_html() -> None:
    if not INDEX.is_file():
        return
    txt = INDEX.read_text(encoding="utf-8")
    txt = OLD_REDIRECT_JS_RE.sub("", txt)
    txt = OLD_SETTINGS_JS_RE.sub("", txt)
    txt = OLD_MENUBAR_STYLE_RE.sub("", txt)
    ins = txt.find("</head>")
    if ins >= 0:
        txt = (
            txt[:ins]
            + INDEX_REDIRECT_JS
            + INDEX_MENUBAR_JS
            + f"<style>{MENUBAR_CSS}</style>\n"
            + txt[ins:]
        )
    INDEX.write_text(txt, encoding="utf-8")
    print("OK index.html: 상단 메뉴 + 설정 탭(#!/1) → SPA")


def _patch_flows(path: Path) -> bool:
    if not path.is_file():
        return False
    raw: list = json.loads(path.read_text(encoding="utf-8-sig"))
    out: list = []
    for n in raw:
        if not isinstance(n, dict):
            out.append(n)
            continue
        nid = n.get("id")
        tab = n.get("tab")
        grp = n.get("group")
        if (
            nid in DROP_NODE_IDS
            or nid in DROP_GROUP_IDS
            or grp in DROP_GROUP_IDS
        ):
            continue
        out.append(n)

    by = {n["id"]: n for n in out if n.get("id")}
    tab = by.get(SETTINGS_TAB_ID)
    if tab:
        tab["name"] = SETTINGS_TAB_NODE["name"]
        tab["icon"] = tab.get("icon") or SETTINGS_TAB_NODE["icon"]
        tab["order"] = SETTINGS_TAB_NODE["order"]
        tab["disabled"] = False
        tab["hidden"] = False
    else:
        out.append(dict(SETTINGS_TAB_NODE))
        by[SETTINGS_TAB_ID] = SETTINGS_TAB_NODE

    _ensure_settings_spa_shell(out, by)

    css = by.get("ui_tpl_css_cronus")
    if css:
        fmt = css.get("format") or ""
        if SETTINGS_TAB_HIDE_CSS not in fmt:
            ins = fmt.find("</style>")
            if ins >= 0:
                fmt = fmt[:ins] + SETTINGS_TAB_HIDE_CSS + fmt[ins:]
        if MENUBAR_CSS_MARK not in fmt:
            ins = fmt.find("</style>")
            if ins >= 0:
                fmt = fmt[:ins] + MENUBAR_CSS + fmt[ins:]
        css["format"] = fmt

    path.write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return True


def main() -> int:
    for fp in FLOW_FILES:
        if _patch_flows(fp):
            print(f"OK {fp.name} (설정 ui_tab+그룹 → sidenav, iframe/중간페이지 제거)")
    _patch_index_html()
    print(f"OK patch_settings_spa → D1 메뉴바 + {SPA_ENTRY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
