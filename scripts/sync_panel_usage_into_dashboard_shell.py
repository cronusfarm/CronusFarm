# -*- coding: utf-8 -*-
"""패널 사용 가이드 HTML을 devflow·Dashboard 1 /ui 쉘에 반영.

정본: nodered/panel_usage_cf_tpl.html (있으면 이 파일 우선).
없으면 flows_cronusfarm_devflow_flow.json 의 cf_tpl_dev_panel_usage.format 을 읽어
Dashboard 1 ui_grp_shell 의 ui_tpl_shell_panel_usage 만 갱신한다.

동기 시 `flows_cronusfarm_devflow_flow.json` 의 `cf_tpl_dev_panel_usage` 외에,
하드웨어 그룹 `cf_tpl_dev_hw_panel` 에 EXP1/EXP2 핀 요약 표가 없으면 삽입한다.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NR = ROOT / "nodered"
NEW_ID = "ui_tpl_shell_panel_usage"
HTML_SRC = NR / "panel_usage_cf_tpl.html"


def load_panel_format() -> str:
    if HTML_SRC.is_file():
        return HTML_SRC.read_text(encoding="utf-8").strip()
    for rel in ("flows_cronusfarm_devflow_flow.json", "merged-deploy.json"):
        p = NR / rel
        if not p.is_file():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        for n in data:
            if n.get("id") == "cf_tpl_dev_panel_usage" and n.get("format"):
                return str(n["format"])
    raise SystemExit("cf_tpl_dev_panel_usage.format 또는 panel_usage_cf_tpl.html 을 찾지 못했습니다.")


def write_devflow_format(fmt: str) -> None:
    p = NR / "flows_cronusfarm_devflow_flow.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    for n in data:
        if n.get("id") == "cf_tpl_dev_panel_usage":
            n["format"] = fmt
            break
    else:
        raise SystemExit("devflow 에 cf_tpl_dev_panel_usage 노드가 없습니다.")
    _patch_dev_hw_panel_pin_tables(data)
    p.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _patch_dev_hw_panel_pin_tables(data: list) -> None:
    """cf_tpl_dev_hw_panel 에 EXP1/EXP2 요약 표 삽입(이미 있으면 스킵)."""
    marker = "</svg>"
    tag = "R3 EXP1 / EXP2 → UNO (CronusFarm 기본)"
    ins = (
        marker
        + '\n<p style="margin:12px 0 6px;font-weight:700;color:#90caf9">'
        + tag
        + '</p>\n<table style="width:100%;border-collapse:collapse;font-size:11px;margin:0 0 10px;color:#ececec">'
        '<thead><tr style="background:rgba(255,255,255,.08)">'
        '<th style="border:1px solid #455a64;padding:3px 4px">EXP1</th>'
        '<th style="border:1px solid #455a64;padding:3px 4px">UNO</th>'
        '<th style="border:1px solid #455a64;padding:3px 4px">역할</th></tr></thead><tbody>'
        '<tr><td style="border:1px solid #455a64;padding:3px 4px">1</td>'
        '<td style="border:1px solid #455a64;padding:3px 4px">D9</td>'
        '<td style="border:1px solid #455a64;padding:3px 4px">부저 (반대 VCC·10)</td></tr>'
        '<tr><td style="border:1px solid #455a64;padding:3px 4px">2</td>'
        '<td style="border:1px solid #455a64;padding:3px 4px">D8</td>'
        '<td style="border:1px solid #455a64;padding:3px 4px">엔코더 클릭</td></tr>'
        '<tr><td style="border:1px solid #455a64;padding:3px 4px">3–8</td>'
        '<td style="border:1px solid #455a64;padding:3px 4px">D7→D2</td>'
        '<td style="border:1px solid #455a64;padding:3px 4px">LCD EN/RS/D4–D7</td></tr>'
        '<tr><td style="border:1px solid #455a64;padding:3px 4px">9</td>'
        '<td style="border:1px solid #455a64;padding:3px 4px">GND</td>'
        '<td style="border:1px solid #455a64;padding:3px 4px">오른쪽 위(확인)</td></tr>'
        '<tr><td style="border:1px solid #455a64;padding:3px 4px">10</td>'
        '<td style="border:1px solid #455a64;padding:3px 4px">5V</td>'
        '<td style="border:1px solid #455a64;padding:3px 4px">VCC 오른쪽 아래</td></tr>'
        "</tbody></table>\n"
        '<table style="width:100%;border-collapse:collapse;font-size:11px;margin:0 0 10px;color:#ececec">'
        '<thead><tr style="background:rgba(255,255,255,.08)">'
        '<th style="border:1px solid #455a64;padding:3px 4px">EXP2</th>'
        '<th style="border:1px solid #455a64;padding:3px 4px">UNO</th>'
        '<th style="border:1px solid #455a64;padding:3px 4px">역할</th></tr></thead><tbody>'
        '<tr><td style="border:1px solid #455a64;padding:3px 4px">1</td>'
        '<td style="border:1px solid #455a64;padding:3px 4px">D12</td>'
        '<td style="border:1px solid #455a64;padding:3px 4px">풀업</td></tr>'
        '<tr><td style="border:1px solid #455a64;padding:3px 4px">2</td>'
        '<td style="border:1px solid #455a64;padding:3px 4px">D10</td>'
        '<td style="border:1px solid #455a64;padding:3px 4px">MISO/SPI (클릭 아님)</td></tr>'
        '<tr><td style="border:1px solid #455a64;padding:3px 4px">3 / 5</td>'
        '<td style="border:1px solid #455a64;padding:3px 4px">A0 / A1</td>'
        '<td style="border:1px solid #455a64;padding:3px 4px">ENC A / B</td></tr>'
        '<tr><td style="border:1px solid #455a64;padding:3px 4px">4</td>'
        '<td style="border:1px solid #455a64;padding:3px 4px">D11</td>'
        '<td style="border:1px solid #455a64;padding:3px 4px">풀업</td></tr>'
        '<tr><td style="border:1px solid #455a64;padding:3px 4px">6</td>'
        '<td style="border:1px solid #455a64;padding:3px 4px">D13</td>'
        '<td style="border:1px solid #455a64;padding:3px 4px">SD CS HIGH</td></tr>'
        "</tbody></table>\n"
        '<p style="margin:0 0 8px;opacity:.85;font-size:11px">전체 표·LCD 상태 상세는 아래 '
        '<code style="color:#ffcc80">cf_tpl_dev_panel_usage</code> 노드와 동일 본문 '
        '<code style="color:#ffcc80">panel_usage_cf_tpl.html</code> — '
        '<code style="color:#ffcc80">python scripts/sync_panel_usage_into_dashboard_shell.py</code></p>'
    )
    for n in data:
        if n.get("id") != "cf_tpl_dev_hw_panel":
            continue
        f = n.get("format", "")
        if tag in f:
            return
        if marker not in f:
            return
        n["format"] = f.replace(marker, ins, 1)
        return


def main() -> None:
    fmt = load_panel_format()
    if HTML_SRC.is_file():
        write_devflow_format(fmt)

    dash_path = NR / "flows_cronusfarm_dashboard.json"
    dash = json.loads(dash_path.read_text(encoding="utf-8"))
    dash = [n for n in dash if n.get("id") != NEW_ID]
    for n in dash:
        if n.get("id") == "ui_tpl_shell_html":
            n["order"] = 2  # 가이드가 위에 오도록 쉘 HTML은 두 번째
    new_node = {
        "id": NEW_ID,
        "type": "ui_template",
        "z": "tab_cronus_dash",
        "group": "ui_grp_shell",
        "name": "사용가이드 (패널 LCD·다이얼)",
        "order": 1,
        "width": "12",
        # Dashboard 1 ui_template height = 그리드 단위. 너무 작으면 긴 HTML이 잘림 → 충분히 크게 + HTML 내부 스크롤
        "height": "85",
        "format": fmt,
        "storeOutMessages": False,
        "fwdInMessages": False,
        "resendOnRefresh": True,
        "templateScope": "local",
        "x": 2580,
        "y": 520,
        "wires": [[]],
    }
    dash.append(new_node)
    dash_path.write_text(json.dumps(dash, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    src = "panel_usage_cf_tpl.html" if HTML_SRC.is_file() else "devflow"
    print("OK", NEW_ID, "source=", src, "chars", len(fmt))


if __name__ == "__main__":
    main()
