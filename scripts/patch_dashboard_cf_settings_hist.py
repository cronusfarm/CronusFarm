# CronusFarm-설정: Bed/스케줄·설정 도구를 nginx 정적 HTML + iframe 으로 삽입(내장 Vue embed 제거).
#
# 권장 실행 순서(한 번에):
#   1) patch_srv_inlay_widgets.py
#   2) patch_nr_panel_doc_and_ui.py
#   3) patch_dashboard_cf_settings_hist.py  (본 스크립트)
#   4) merge_nodered_deploy.py --use-split
#
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

SETTINGS_GRP_BEDS = {
    "id": "ui_grp_settings_beds",
    "type": "ui_group",
    "name": "Bed 제어 · 스케줄",
    "tab": "ui_tab_settings",
    "order": 1,
    "disp": True,
    "width": "12",
    "collapse": False,
    "className": "",
}

SETTINGS_GRP_TOOLS = {
    "id": "ui_grp_settings_tools",
    "type": "ui_group",
    "name": "스케줄 API · 관제 허브",
    "tab": "ui_tab_settings",
    "order": 2,
    "disp": True,
    "width": "12",
    "collapse": False,
    "className": "",
}

# 구형 per-채널 히스토그램·내장 embed 노드 제거
HIST_REMOVE_IDS = frozenset(
    {
        "ui_tpl_hist_led_a1",
        "ui_tpl_hist_led_a2",
        "ui_tpl_hist_pump_a1",
        "ui_tpl_hist_pump_a2",
        "ui_tpl_hist_fan_a1",
        "ui_tpl_hist_fan_a2",
        "ui_tpl_hist_led_b1",
        "ui_tpl_hist_pump_b1",
        "ui_tpl_hist_pump_b2",
        "ui_tpl_hist_fan_b1",
        "ui_tpl_hist_fan_b2",
        "ui_tpl_hist_combo_a",
        "ui_tpl_hist_combo_b",
        "ui_tpl_settings_beds_embed",
    }
)

IFRAME_CSS = """
/* 설정 탭 iframe: 카드 높이·스크롤 */
body.nr-dashboard-theme .nr-dashboard-template:has(.cf-settings-iframe-wrap),
body.nr-dashboard-theme .nr-dashboard-template:has(.cf-settings-iframe-wrap) md-card-content{
  overflow:visible!important;max-height:none!important;height:auto!important;}
.cf-settings-iframe-wrap{width:100%;box-sizing:border-box;border-radius:12px;overflow:hidden;
  border:1px solid rgba(45,255,122,.12);background:rgba(0,0,0,.2);}
.cf-settings-iframe-wrap iframe{display:block;width:100%;min-height:520px;height:72vh;border:0;background:#040d07;}
@media(max-width:720px){.cf-settings-iframe-wrap iframe{min-height:480px;height:65vh;}}
"""


def iframe_template(*, node_id: str, name: str, src_path: str, order: int, height: str) -> dict:
    fmt = (
        '<div class="cf-settings-iframe-wrap">'
        f'<iframe title="{name}" loading="lazy" '
        'sandbox="allow-scripts allow-same-origin allow-forms allow-popups" '
        f'src="{src_path}"></iframe>'
        "</div>"
        "<style>"
        + IFRAME_CSS.strip()
        + "</style>"
    )
    return {
        "id": node_id,
        "type": "ui_template",
        "z": "tab_cronus_dash",
        "group": "ui_grp_settings_beds" if "beds" in node_id else "ui_grp_settings_tools",
        "name": name,
        "order": order,
        "width": "12",
        "height": height,
        "format": fmt,
        "storeOutMessages": False,
        "fwdInMessages": False,
        "resendOnRefresh": True,
        "templateScope": "local",
        "x": 100,
        "y": 1200,
        "wires": [[]],
    }


def upsert_node(nodes: list, node: dict) -> None:
    nid = node["id"]
    for i, n in enumerate(nodes):
        if isinstance(n, dict) and n.get("id") == nid:
            nodes[i] = node
            return
    nodes.append(node)


def main() -> None:
    nodes = json.loads(DASH.read_text(encoding="utf-8-sig"))
    nodes = [n for n in nodes if n.get("id") not in HIST_REMOVE_IDS]

    have_beds_grp = any(
        isinstance(n, dict) and n.get("id") == "ui_grp_settings_beds" for n in nodes
    )
    if not have_beds_grp:
        nodes.append(SETTINGS_GRP_BEDS)
    have_tools_grp = any(
        isinstance(n, dict) and n.get("id") == "ui_grp_settings_tools" for n in nodes
    )
    if not have_tools_grp:
        nodes.append(SETTINGS_GRP_TOOLS)

    beds_if = iframe_template(
        node_id="ui_tpl_settings_beds_iframe",
        name="Bed/스케줄 (iframe)",
        src_path="/cronusfarm-static/cronusfarm_d1_settings_beds_sched.html",
        order=1,
        height="72",
    )
    tools_if = iframe_template(
        node_id="ui_tpl_settings_tools_iframe",
        name="스케줄 API·관제 (iframe)",
        src_path="/cronusfarm-static/cronusfarm_d1_settings_tools.html",
        order=1,
        height="56",
    )

    upsert_node(nodes, beds_if)
    upsert_node(nodes, tools_if)

    DASH.write_text(json.dumps(nodes, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(
        "OK dashboard: settings iframes",
        beds_if["id"],
        tools_if["id"],
        "removed_embed=",
        "ui_tpl_settings_beds_embed" in HIST_REMOVE_IDS,
    )


if __name__ == "__main__":
    main()
