"""
NRDB2(/nrdb2/settings) 설정 화면 UI 패치.

요구사항
- Auto/Manual → 자동/수동(한글)
- "A/B Bed · 채널" 제목 제거
- 자동 안내문구는 페이지 최하단에 1회만 표시
- 채널(장치) 이름 강조(가독성)
- 배경을 /ui 모니터처럼 더 어둡게
- 버튼 입체(3D) 느낌 강화
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
from nrdb2_bed_format import build_nrdb2_bed_format, extract_channels_inner  # noqa: E402
from nrdb2_schedule_ui_format import build_nrdb2_schedule_format  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
FLOW_PATH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

# 대상 ui-template 노드 id (이 저장소 기준)
ID_A = "f1e2d3c4b5a6f011"  # A Bed · AUTO/MANUAL 버튼
ID_B = "f1e2d3c4b5a6f012"  # B Bed · AUTO/MANUAL 버튼
ID_CSS = "f1e2d3c4b5a6f010"  # NRDB2 설정 페이지 CSS (page:style)

# 신규 추가(설정/NRDB2)
ID_C = "f1e2d3c4b5a6f013"  # C Bed · AUTO/MANUAL 버튼(추가)
ID_D = "f1e2d3c4b5a6f014"  # D Bed · AUTO/MANUAL 버튼(추가)
G_C = "f1e2d3c4b5a68008"  # C Bed 그룹(추가)
G_D = "f1e2d3c4b5a68009"  # D Bed 그룹(추가)
PAGE_SETTINGS = "f1e2d3c4b5a68003"
TAB_Z = "tab_cronus_dash"
WIRE_OUT = "f1e2d3c4b5a6800f"

# 스케줄 변경 UI(추가)
G_SCHEDULE = "f1e2d3c4b5a6800a"
ID_SCHEDULE_UI = "f1e2d3c4b5a6f020"


def _patch_vue_template(fmt: str, *, add_global_help: bool) -> str:
    # 1) 배지: toLowerCase 기반 → 자동/수동 기준 클래스
    fmt = fmt.replace(
        '<span class="badge" :class="ch.mode.toLowerCase()">{{ ch.mode }}</span>',
        '<span class="badge" :class="(ch.mode===\'자동\'?\'auto\':\'manual\')">{{ ch.mode }}</span>',
    )

    # 2) 제목 제거
    fmt = fmt.replace('title: "A Bed · 채널",', 'title: "",')
    fmt = fmt.replace('title: "B Bed · 채널",', 'title: "",')

    # 3) 모드 문자열/로직 한글화
    fmt = fmt.replace("mode: 'AUTO'", "mode: '자동'")
    fmt = fmt.replace("ch.mode === 'AUTO'", "ch.mode === '자동'")
    fmt = fmt.replace("ch.mode = 'MANUAL'", "ch.mode = '수동'")
    fmt = fmt.replace("ch.mode = 'AUTO'", "ch.mode = '자동'")
    fmt = fmt.replace("ch.mode !== 'MANUAL'", "ch.mode !== '수동'")

    # 4) 힌트/설명: 자동 안내는 제거(최하단 1회로)
    fmt = fmt.replace(
        "return ch.mode === 'AUTO' ? '스케줄 동작 중' : '직접 제어 중'",
        "return ch.mode === '자동' ? '스케줄 동작 중' : '직접 제어 중'",
    )
    fmt = fmt.replace(
        "if (ch.mode === 'AUTO') {\n        return '자동 스케줄에 따라 동작 중입니다.<br>길게 누르면 수동으로 전환됩니다.'\n      }",
        "if (ch.mode === '자동') {\n        return ''\n      }",
    )

    # 5) 스타일: 타이틀 숨김, 채널명 강조, 버튼 3D, 배지 색상 다크톤
    fmt = fmt.replace(
        ".cf2-bed { display: flex; flex-direction: column; gap: 14px; font-family: sans-serif; }",
        ".cf2-bed { display: flex; flex-direction: column; gap: 14px; font-family: -apple-system,BlinkMacSystemFont,\"Segoe UI\",Roboto,sans-serif; }",
    )
    fmt = fmt.replace(
        ".cf2-bed-hd { font-size: 11px; font-weight: 800; color: #9db0cc; letter-spacing: 0.08em; text-transform: uppercase; }",
        ".cf2-bed-hd { display:none; }",
    )
    fmt = fmt.replace(
        ".cf2-name { font-size: 13px; font-weight: 800; color: #e6edf7; }",
        ".cf2-name { font-size: 16px; font-weight: 900; color: #e6edf7; letter-spacing: .01em; }",
    )
    fmt = fmt.replace(
        "border: 2px solid #ccc;\n  background: #ffffff;",
        "border: 1px solid rgba(255,255,255,.12);\n  background: linear-gradient(180deg, rgba(255,255,255,.16), rgba(255,255,255,.08));\n  box-shadow: 0 10px 22px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.12);",
    )
    fmt = fmt.replace(
        "transition: background 0.15s, border-color 0.2s, transform 0.1s;",
        "transition: background 0.15s, border-color 0.2s, transform 0.1s, box-shadow 0.2s;",
    )
    fmt = fmt.replace(
        ".ctrlBtn:hover { background: #f5f5f5; }",
        ".ctrlBtn:hover { box-shadow: 0 12px 28px rgba(0,0,0,.42), inset 0 1px 0 rgba(255,255,255,.14); }",
    )
    fmt = fmt.replace(
        ".ctrlBtn:active { transform: scale(0.96); }",
        ".ctrlBtn:active { transform: translateY(1px) scale(0.98); box-shadow: 0 7px 18px rgba(0,0,0,.38), inset 0 1px 0 rgba(255,255,255,.1); }",
    )
    fmt = fmt.replace(
        ".ctrlBtn.is-on { border-color: #1D9E75; }",
        ".ctrlBtn.is-on {\n  border-color: rgba(52,199,89,.6);\n"
        "  background: linear-gradient(180deg, rgba(52,199,89,.45), rgba(52,199,89,.16));\n}",
    )
    fmt = fmt.replace(
        ".ctrlBtn.is-off { border-color: #D85A30; }",
        ".ctrlBtn.is-off {\n  border-color: rgba(255,59,48,.55);\n"
        "  background: linear-gradient(180deg, rgba(255,59,48,.38), rgba(255,59,48,.14));\n}",
    )
    fmt = fmt.replace(
        ".badge.auto { background: #E6F1FB; color: #185FA5; border-color: #85B7EB; }",
        ".badge.auto { background: rgba(52,199,89,.32); color: #d6ffe3; border-color: rgba(52,199,89,.55); }",
    )
    fmt = fmt.replace(
        ".badge.manual { background: #EAF3DE; color: #3B6D11; border-color: #97C459; }",
        ".badge.manual { background: rgba(255,193,7,.32); color: #fff2c2; border-color: rgba(255,193,7,.55); }",
    )

    # 배지(자동/수동) 글자 크게
    fmt = fmt.replace("font-size: 10px;\n", "font-size: 14px;\n")
    fmt = fmt.replace("padding: 2px 8px;\n", "padding: 5px 12px;\n")

    # 6) 중복 제거
    # - 템플릿 내부 하단 도움말(cf2-help)은 제거하고, page:style에서 1회만 노출
    # - 각 채널 아래 statusText는 제거(세로 높이 축소 → 스크롤 완화)
    fmt = re.sub(r"\n\s*<div class=\"cf2-help\">.*?</div>\n", "\n", fmt, flags=re.S)
    fmt = re.sub(r"\n\.cf2-help\{[^}]*\}\n", "\n", fmt, flags=re.S)

    fmt = fmt.replace("\n        <div class=\"statusText\" v-html=\"statusHtml(ch)\"></div>", "")
    fmt = fmt.replace("\n        <div class=\"statusText\" v-html=\"statusHtml(ch)\"></div>\n", "\n")
    fmt = fmt.replace("\n.statusText {\n", "\n/* statusText 제거(세로 스크롤 방지) */\n.statusText {\n")
    fmt = fmt.replace("max-width: 180px;\n}\n", "max-width: 180px;\n  display:none;\n}\n")

    # 이미 한 번 패치된 플로우(테두리만 있던 경우) — ON/OFF 버튼 배경 채움
    fmt = fmt.replace(
        ".ctrlBtn.is-on { border-color: rgba(52,199,89,.55); }",
        ".ctrlBtn.is-on {\n  border-color: rgba(52,199,89,.6);\n"
        "  background: linear-gradient(180deg, rgba(52,199,89,.45), rgba(52,199,89,.16));\n}",
    )
    fmt = fmt.replace(
        ".ctrlBtn.is-off { border-color: rgba(255,59,48,.55); }",
        ".ctrlBtn.is-off {\n  border-color: rgba(255,59,48,.55);\n"
        "  background: linear-gradient(180deg, rgba(255,59,48,.38), rgba(255,59,48,.14));\n}",
    )

    # 직접 제어/스케줄 문구 → 장치명 아래로 + 카드 여백 최소화
    fmt = _layout_cf2_template(fmt)
    return fmt


def _layout_cf2_template(fmt: str) -> str:
    """버튼 안 subHint 제거, 장비명 아래 cf2-modehint로 이동. 채널행 간격 축소."""
    if "cf2-modehint" not in fmt:
        fmt = fmt.replace(
            '<div class="cf2-name">{{ ch.label }} <span class="cf2-pin">{{ ch.pin }}</span></div>\n'
            "      </div>",
            '<div class="cf2-name">{{ ch.label }} <span class="cf2-pin">{{ ch.pin }}</span></div>\n'
            '        <div class="cf2-modehint">{{ subHint(ch) }}</div>\n'
            "      </div>",
        )
    fmt = re.sub(r"\n\s*<span class=\"subHint\">\{\{ subHint\(ch\) \}\}</span>", "", fmt)

    fmt = fmt.replace(".cf2-bed { display: flex; flex-direction: column; gap: 14px;", ".cf2-bed { display: flex; flex-direction: column; gap: 8px;")
    fmt = fmt.replace("gap: 14px; font-family:", "gap: 8px; font-family:")
    fmt = fmt.replace(
        "padding: 10px 12px;",
        "padding: 6px 10px;",
    )
    fmt = fmt.replace(".cf2-chinfo { min-width: 0; padding-top: 8px; }", ".cf2-chinfo { min-width: 0; padding-top: 2px; }")

    fmt = fmt.replace(
        ".subHint { font-size: 11px; color: #888; }",
        ".cf2-modehint { font-size: 11px; color: #9db0cc; margin-top: 4px; font-weight: 600; line-height: 1.35; }",
    )
    # ON/OFF 글자색 — 버튼 배경이 채워져 대비 유지
    fmt = fmt.replace(
        ".mainState.on { color: #0F6E56; }",
        ".mainState.on { color: #eafff3; text-shadow: 0 1px 2px rgba(0,0,0,.35); }",
    )
    fmt = fmt.replace(
        ".mainState.off { color: #993C1D; }",
        ".mainState.off { color: #ffe8e4; text-shadow: 0 1px 2px rgba(0,0,0,.35); }",
    )
    return fmt


def _patch_page_css(fmt: str) -> str:
    # /ui 모니터 느낌(더 어둡고, app 배경 투명)
    fmt = fmt.replace(
        "--cf2-card: rgba(15, 27, 49, 0.92);",
        "--cf2-card: rgba(15, 27, 49, 0.86);",
    )
    fmt = fmt.replace(
        "background: linear-gradient(180deg, var(--cf2-bg0) 0%, var(--cf2-bg1) 45%, #050a12 100%) !important;",
        "background: linear-gradient(180deg, var(--cf2-bg0) 0%, var(--cf2-bg1) 60%, #070c15 100%) !important;",
    )

    # 핵심: 실제 배경은 className이 아니라 html/body/.v-application 쪽에서 결정되는 경우가 있어
    # page:style 안에서 Vuetify 루트까지 직접 강제로 덮어씁니다.
    if "html body .v-application" not in fmt:
        fmt = fmt.replace(
            "/* NRDB2 설정 전용 — 모니터 cf-tile 톤(다크 글래스) */\n",
            "/* NRDB2 설정 전용 — 모니터 cf-tile 톤(다크 글래스) */\n"
            "/* 배경이 안 바뀌는 경우가 있어, page:style 안에서 html/body/Vuetify 루트까지 강제로 덮어씁니다. */\n"
            "html, body{ background: #070c15 !important; }\n"
            "html body .v-application, html body .v-main, html body .v-application__wrap{\n"
            "  background: linear-gradient(180deg, #070c15 0%, #0b1220 60%, #070c15 100%) !important;\n"
            "  background-color: #070c15 !important;\n"
            "}\n",
        )
    # 배경이 실제로 적용되는 루트가 환경마다 달라(.v-application / .v-application__wrap / .v-main),
    # className(nrdb-settings-page)이 어디에 붙어도 어두운 배경이 강제되도록 셀렉터를 넓게 추가합니다.
    if "className(nrdb-settings-page)" not in fmt:
        fmt = fmt.replace(
            "/* NRDB2 설정 전용 — 모니터 cf-tile 톤(다크 글래스) */\n",
            "/* NRDB2 설정 전용 — 모니터 cf-tile 톤(다크 글래스) */\n"
            "/* 주의: className(nrdb-settings-page)이 어느 엘리먼트에 붙어도 배경이 어둡게 고정되도록 셀렉터를 넓게 잡습니다. */\n",
        )

    if ".v-application__wrap" not in fmt:
        fmt = fmt.replace(
            ".nrdb-settings-page, .nrdb-settings-page .v-main {",
            ".nrdb-settings-page,\n"
            ".nrdb-settings-page .v-main,\n"
            ".nrdb-settings-page .v-application,\n"
            ".nrdb-settings-page .v-application__wrap,\n"
            ".v-application.nrdb-settings-page,\n"
            ".v-application.nrdb-settings-page .v-main,\n"
            ".v-application.nrdb-settings-page .v-application__wrap,\n"
            ".v-main.nrdb-settings-page {",
        )
        fmt = fmt.replace(
            "background: linear-gradient(180deg, var(--cf2-bg0) 0%, var(--cf2-bg1) 60%, #070c15 100%) !important;",
            "background: linear-gradient(180deg, var(--cf2-bg0) 0%, var(--cf2-bg1) 60%, #070c15 100%) !important;\n"
            "  background-color: #070c15 !important;",
        )

    if ".nrdb-settings-page .v-application__wrap" not in fmt:
        fmt = fmt.replace(
            ".nrdb-settings-page .v-application{ background: transparent !important; }",
            ".nrdb-settings-page .v-application,\n"
            ".v-application.nrdb-settings-page{ background: transparent !important; }\n"
            ".nrdb-settings-page .v-application__wrap,\n"
            ".v-application.nrdb-settings-page .v-application__wrap{ background: transparent !important; }",
        )

    if ".nrdb-settings-page .v-application" not in fmt:
        fmt = fmt.replace(
            "}\n.nrdb-settings-page .v-card, .nrdb-settings-page .v-sheet {",
            "}\n.nrdb-settings-page .v-application{ background: transparent !important; }\n.nrdb-settings-page .v-card, .nrdb-settings-page .v-sheet {",
        )
    fmt = fmt.replace(
        "box-shadow: 0 12px 40px rgba(0, 0, 0, 0.35) !important;",
        "box-shadow: 0 14px 44px rgba(0, 0, 0, 0.45) !important;",
    )
    # 도움말: 페이지 최하단 — 사용안내 제목 + 큰 글자 (NRDB2_HELP_V2)
    fmt = re.sub(
        r"/\* NRDB2_HELP_ONCE:[\s\S]*?white-space: pre-line;\s*\}\s*\n*",
        "",
        fmt,
        count=1,
    )
    if "NRDB2_HELP_V2" not in fmt:
        fmt = fmt.replace(
            "/* 펌프 그룹 */\n",
            "/* NRDB2_HELP_V2: 사용안내(페이지 최하단, 한 번만) */\n"
            ".nrdb-settings-page .v-main::before,\n"
            ".v-main.nrdb-settings-page::before{\n"
            "  content: '사용안내';\n"
            "  display:block;\n"
            "  margin: 18px 0 6px;\n"
            "  padding: 0 12px;\n"
            "  font-size: 14px;\n"
            "  font-weight: 900;\n"
            "  letter-spacing: .02em;\n"
            "  color: #e6edf7;\n"
            "}\n"
            ".nrdb-settings-page .v-main::after,\n"
            ".v-main.nrdb-settings-page::after{\n"
            "  content: '자동 : 스케줄에 따라 동작합니다.\\A수동 : 직접 제어 합니다.\\A길게 누르면 자동/수동으로 전환됩니다.';\n"
            "  display:block;\n"
            "  margin: 0 0 8px;\n"
            "  padding: 14px 16px;\n"
            "  border-radius: 14px;\n"
            "  background: rgba(255,255,255,.06);\n"
            "  border: 1px solid rgba(255,255,255,.1);\n"
            "  color: #d6e3fb;\n"
            "  font-size: 15px;\n"
            "  font-weight: 650;\n"
            "  line-height: 1.7;\n"
            "  white-space: pre-line;\n"
            "}\n\n"
            "/* 펌프 그룹 */\n",
        )
    # Bed 카드·그룹: 내용 높이만큼만 (빈 여백 축소)
    if "NRDB2_BED_AUTOSIZE" not in fmt:
        fmt = fmt.replace(
            "</style>",
            "/* NRDB2_BED_AUTOSIZE */\n"
            ".nrdb-settings-page .nrdb-ui-group,\n"
            ".nrdb-settings-page .nrdb-ui-group .v-card,\n"
            ".nrdb-settings-page .nrdb-ui-group .v-sheet{\n"
            "  height: auto !important;\n"
            "  min-height: 0 !important;\n"
            "}\n"
            ".nrdb-settings-page .nrdb-ui-group .nrdb-ui-widget{\n"
            "  height: auto !important;\n"
            "  min-height: 0 !important;\n"
            "}\n"
            "</style>",
            1,
        )
    return fmt


def _drop_nodes_for_groups(flows: list, *, group_ids: set[str]) -> list:
    # group 자체 + 해당 group을 참조하는 위젯 전부 제거
    out = []
    for n in flows:
        if not isinstance(n, dict):
            continue
        if n.get("id") in group_ids:
            continue
        if n.get("group") in group_ids:
            continue
        out.append(n)
    return out


def _ensure_group(by_id: dict, flows: list, *, gid: str, name: str, order: int) -> None:
    if gid in by_id:
        return
    flows.append(
        {
            "id": gid,
            "type": "ui-group",
            "name": name,
            "page": PAGE_SETTINGS,
            "width": "6",
            "height": "1",
            "order": order,
            "showTitle": True,
            "className": "",
            "visible": "true",
            "disabled": "false",
            "groupType": "default",
        }
    )
    by_id[gid] = flows[-1]


def _schedule_stub_format() -> str:
    """스케줄 변경하기 — cronusfarm_sqlite_bridge GET/PUT /api/schedule 연동."""
    return build_nrdb2_schedule_format()


def _ensure_schedule_ui(by_id: dict, flows: list) -> None:
    _ensure_group(by_id, flows, gid=G_SCHEDULE, name="스케줄 변경하기", order=5)
    fmt = _schedule_stub_format()
    if ID_SCHEDULE_UI in by_id:
        by_id[ID_SCHEDULE_UI]["format"] = fmt
        by_id[ID_SCHEDULE_UI]["height"] = "14"
        return
    flows.append(
        {
            "id": ID_SCHEDULE_UI,
            "type": "ui-template",
            "z": TAB_Z,
            "group": G_SCHEDULE,
            "page": "",
            "ui": "",
            "name": "스케줄 변경 UI(초안)",
            "order": 0,
            "width": "12",
            "height": "14",
            "head": "",
            "format": fmt,
            "storeOutMessages": True,
            "passthru": True,
            "resendOnRefresh": True,
            "templateScope": "local",
            "className": "",
            "x": 200,
            "y": 1660,
            "wires": [[]],
        }
    )
    by_id[ID_SCHEDULE_UI] = flows[-1]


def _new_bed_template(*, tid: str, group: str, name: str, channels_js: str, y: int) -> dict:
    # A/B/C/D 동일: nrdb2_bed_format.build 로 통일
    fmt = build_nrdb2_bed_format(channels_js.rstrip())
    return {
        "id": tid,
        "type": "ui-template",
        "z": TAB_Z,
        "group": group,
        "page": "",
        "ui": "",
        "name": name,
        "order": 0,
        "width": "6",
        "height": "0",
        "head": "",
        "format": fmt,
        "storeOutMessages": True,
        "passthru": False,
        "resendOnRefresh": True,
        "templateScope": "local",
        "className": "",
        "x": 200,
        "y": y,
        "wires": [[WIRE_OUT]],
    }


def main() -> None:
    flows = json.loads(FLOW_PATH.read_text(encoding="utf-8"))
    by_id = {n.get("id"): n for n in flows if isinstance(n, dict)}

    for nid in (ID_A, ID_B):
        if nid not in by_id:
            raise SystemExit(f"missing node: {nid}")

    ncss = by_id.get(ID_CSS)
    if not ncss:
        raise SystemExit(f"missing css node: {ID_CSS}")
    ncss["format"] = _patch_page_css(ncss.get("format", ""))

    # C/D Bed 그룹 + 템플릿 추가(없으면 생성)
    _ensure_group(by_id, flows, gid=G_C, name="C Bed", order=3)
    _ensure_group(by_id, flows, gid=G_D, name="D Bed", order=4)

    if ID_C not in by_id:
        flows.append(
            _new_bed_template(
                tid=ID_C,
                group=G_C,
                name="C Bed · AUTO/MANUAL 버튼",
                channels_js=(
                    "        { t: 'pump_c1', at: 'auto_pump_c1', label: 'Pump C1', pin: '(R4-A0)', mode: '자동', state: 'ON', holding: false, holdPct: 0, holdFired: false, _holdT: null, _holdI: null },\n"
                    "        { t: 'pump_c2', at: 'auto_pump_c2', label: 'Pump C2', pin: '(R4-A1)', mode: '자동', state: 'ON', holding: false, holdPct: 0, holdFired: false, _holdT: null, _holdI: null }\n"
                ),
                y=1440,
            )
        )
        by_id[ID_C] = flows[-1]

    if ID_D not in by_id:
        flows.append(
            _new_bed_template(
                tid=ID_D,
                group=G_D,
                name="D Bed · AUTO/MANUAL 버튼",
                channels_js=(
                    "        { t: 'pump_d1', at: 'auto_pump_d1', label: 'Pump D1', pin: '(R4-A2)', mode: '자동', state: 'ON', holding: false, holdPct: 0, holdFired: false, _holdT: null, _holdI: null },\n"
                    "        { t: 'pump_d2', at: 'auto_pump_d2', label: 'Pump D2', pin: '(R4-A3)', mode: '자동', state: 'ON', holding: false, holdPct: 0, holdFired: false, _holdT: null, _holdI: null }\n"
                ),
                y=1540,
            )
        )
        by_id[ID_D] = flows[-1]

    # A/B/C/D 동일 Bed 카드 (채널 JSON 추출 → 통일 템플릿 재생성)
    for nid in (ID_A, ID_B, ID_C, ID_D):
        n = by_id.get(nid)
        if not n:
            continue
        inner = extract_channels_inner(n.get("format", ""))
        if inner:
            n["format"] = build_nrdb2_bed_format(inner)
        else:
            n["format"] = _patch_vue_template(n.get("format", ""), add_global_help=False)
        n["height"] = "0"

    # 스케줄 변경 섹션(초안) 생성
    _ensure_schedule_ui(by_id, flows)

    # 2) 펌프 시간(드롭다운) 삭제 — 설정/NRDB2 전용
    pump_groups = {"f1e2d3c4b5a68006", "f1e2d3c4b5a68007"}
    flows = _drop_nodes_for_groups(flows, group_ids=pump_groups)

    FLOW_PATH.write_text(json.dumps(flows, ensure_ascii=False, indent=4), encoding="utf-8")
    print("OK", FLOW_PATH)


if __name__ == "__main__":
    main()

