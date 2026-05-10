# ui_tpl_status_line 레이아웃을 cf-row-pi-srv(Mosquitto 행)와 동일 패턴으로 정리
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

NEW_FMT = """<div class="cf-row cf-row-pi-srv" style="align-items:flex-start;min-width:0;width:100%;box-sizing:border-box;"><div style="display:flex;flex-direction:column;gap:1px;min-width:0;flex:1;"><div class="cf-label">R4 MQTT</div><div class="cf-muted" style="font-size:10px;line-height:1.2;opacity:.85">Pi(ida) Mosquitto 붙음 — tele 수신 시 online (~15s)</div></div><div style="display:flex;align-items:center;justify-content:flex-end;gap:10px;flex-shrink:0;padding-top:1px;margin-left:10px;"><div class="cf-dot" ng-class="msg._ok ? 'cf-dot-on' : 'cf-dot-off'"></div><div style="font-size:12px;color:var(--cf-text);white-space:nowrap;font-variant-numeric:tabular-nums;text-align:right;">{{msg._ok ? 'online' : 'offline'}}</div></div></div>"""


def main() -> None:
    data = json.loads(p.read_text(encoding="utf-8-sig"))
    for n in data:
        if isinstance(n, dict) and n.get("id") == "ui_tpl_status_line":
            n["format"] = NEW_FMT
            break
    else:
        raise SystemExit("ui_tpl_status_line 없음")
    p.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("OK", p)


if __name__ == "__main__":
    main()
