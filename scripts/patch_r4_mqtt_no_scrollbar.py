# R4 MQTT 템플릿: 높이 1유닛·두 줄 압축, 세로 스크롤바 없음
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

NEW_ROW = """<div class="cf-row cf-row-pi-srv cf-r4-mqtt-strip" style="align-items:center;min-width:0;width:100%;box-sizing:border-box;padding:0;margin:0;"><div style="display:flex;flex-direction:column;gap:0;min-width:0;flex:1;"><div style="font-size:12px;font-weight:800;color:var(--cf-text);line-height:1.1;margin:0;padding:0;">R4 MQTT</div><div style="font-size:9px;line-height:1.1;color:var(--cf-muted);opacity:.9;margin:0;padding:0;margin-top:1px;">Pi(ida) Mosquitto 붙음 — tele 수신 시 online (~15s)</div></div><div style="display:flex;align-items:center;justify-content:flex-end;gap:8px;flex-shrink:0;margin-left:8px;"><div class="cf-dot" ng-class="msg._ok ? 'cf-dot-on' : 'cf-dot-off'"></div><div style="font-size:12px;color:var(--cf-text);white-space:nowrap;font-variant-numeric:tabular-nums;line-height:1.1;">{{msg._ok ? 'online' : 'offline'}}</div></div></div>"""

NEW_CSS = """/* R4 MQTT: 높이 1유닛·두 줄 — 스크롤바 숨기고 세로 여백 최소화 */
.nr-dashboard-theme .nr-dashboard-group .nr-dashboard-template:has(.cf-r4-mqtt-strip){
  overflow: hidden !important;
  overflow-y: hidden !important;
}
.nr-dashboard-theme .nr-dashboard-group .nr-dashboard-template:has(.cf-r4-mqtt-strip) .cf-row.cf-r4-mqtt-strip{
  padding-top: 0 !important;
  padding-bottom: 0 !important;
  align-items: center !important;
}
"""


def main() -> None:
    data = json.loads(p.read_text(encoding="utf-8-sig"))
    for n in data:
        if isinstance(n, dict) and n.get("id") == "ui_tpl_status_line":
            n["format"] = NEW_ROW
            n["height"] = "1"
            break
    else:
        raise SystemExit("ui_tpl_status_line 없음")

    for n in data:
        if isinstance(n, dict) and n.get("id") == "ui_tpl_css_tiles_v1":
            fmt = n.get("format", "")
            start = fmt.find("/* R4 MQTT")
            if start >= 0:
                end = fmt.find("</style>", start)
                if end < 0:
                    raise SystemExit("tiles css: </style> 없음")
                fmt = fmt[:start] + NEW_CSS + fmt[end:]
            else:
                needle = "</style>"
                if needle not in fmt:
                    raise SystemExit("tiles css 닫는 태그 없음")
                fmt = fmt.replace(needle, "\n" + NEW_CSS + needle, 1)
            n["format"] = fmt
            break
    else:
        raise SystemExit("ui_tpl_css_tiles_v1 없음")

    p.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("OK", p)


if __name__ == "__main__":
    main()
