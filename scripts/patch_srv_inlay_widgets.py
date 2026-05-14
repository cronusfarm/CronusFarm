# System(Node-RED·Mosquitto)·R4 MQTT: cf-srv-inlay / 펌프 가드 제목–내부 박스 간격 축소
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

FMT_R4 = """<div class="cf-srv-inlay">
  <div class="cf-srv-inlay-bar">
    <div class="cf-srv-inlay-text">
      <div class="cf-srv-inlay-title">R4 MQTT</div>
      <div class="cf-srv-inlay-sub">Pi(ida) Mosquitto 붙음 — tele 수신 시 online (~15s)</div>
    </div>
    <div class="cf-srv-inlay-status">
      <div class="cf-dot" ng-class="msg._ok ? 'cf-dot-on' : 'cf-dot-off'"></div>
      <span class="cf-srv-inlay-st">{{msg._ok ? 'online' : 'offline'}}</span>
    </div>
  </div>
</div>"""

FMT_MOSQ = """<div class="cf-srv-inlay">
  <div class="cf-srv-inlay-bar">
    <div class="cf-srv-inlay-text">
      <div class="cf-srv-inlay-title">Mosquitto</div>
      <div class="cf-srv-inlay-sub">Pi 로컬 브로커(systemd). R4가 붙었는지는 Arduino 카드 「R4 MQTT」 줄(tele) 참고.</div>
    </div>
    <div class="cf-srv-inlay-status">
      <div class="cf-dot" ng-class="msg._ok ? 'cf-dot-on' : 'cf-dot-off'"></div>
      <span class="cf-srv-inlay-st">{{msg._ok ? 'online' : 'offline'}}</span>
    </div>
  </div>
</div>"""

FMT_NR = """<div class="cf-srv-inlay">
  <div class="cf-srv-inlay-bar">
    <div class="cf-srv-inlay-text cf-srv-inlay-text--compact">
      <div class="cf-srv-inlay-title">Node-RED</div>
    </div>
    <div class="cf-srv-inlay-status">
      <div class="cf-dot" ng-class="msg._ok ? 'cf-dot-on' : 'cf-dot-off'"></div>
      <span class="cf-srv-inlay-st">{{msg._ok ? 'online' : 'offline'}}</span>
    </div>
  </div>
</div>"""

FMT_TELE_GUARD = """<div class="cf-tele-guard-ui cf-fe-wide cf-arduino-stack-gap0" style="width:100%;max-width:100%;box-sizing:border-box;margin-bottom:-16px"><div class="cf-ar-title-nogap">펌프 가드 <span class="cf-muted">(tele G:)</span></div><pre class="cf-tele-guard-pre" ng-class="{'cf-guard-warn': (msg.payload||'').toString().indexOf('mx')>=0 || (msg.payload||'').toString().indexOf('mf')>=0, 'cf-guard-ok': (msg.payload||'').toString()==='ok', 'cf-guard-legacy': (msg.payload||'').toString().indexOf('—')===0}" ng-bind="msg.payload"></pre></div><style>.cf-tele-guard-ui{margin:0;padding:0;display:flex;flex-direction:column;gap:0;width:100%!important;max-width:100%!important;min-width:0;overflow:visible!important}.cf-tele-guard-ui .cf-ar-title-nogap{margin:0!important;padding:0 0 1px!important;line-height:1.1!important;font-size:12px;color:var(--cf-muted,#9db0cc)}.cf-tele-guard-pre{display:block;margin:0!important;padding:2px 6px 2px!important;width:100%!important;min-width:0;box-sizing:border-box!important;font-size:11.5px;line-height:1.25;color:#e6edf7;white-space:pre-wrap;word-break:break-word;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.14);border-radius:8px;min-height:1.15em;max-height:2.8em;overflow:hidden}.cf-guard-ok{border-color:rgba(40,167,69,.5)!important;background:rgba(40,167,69,.08)!important}.cf-guard-warn{border-color:rgba(255,193,7,.6)!important;background:rgba(255,193,7,.1)!important}.cf-guard-legacy{border-color:rgba(157,176,204,.35)!important;background:rgba(255,255,255,.04)!important}</style>"""

OLD_TILES_R4_CSS = """/* R4 MQTT: 높이 1유닛·두 줄 — 스크롤바 숨기고 세로 여백 최소화 */
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

NEW_TILES_SRV_CSS = """/* R4 MQTT·Mosquitto: retain 줄과 같은 안쪽 박스(cf-mqtt-unified-bar 계열) */
.nr-dashboard-theme .nr-dashboard-group .nr-dashboard-template:has(.cf-srv-inlay){
  overflow: hidden !important;
  overflow-y: hidden !important;
}
.cf-srv-inlay{
  margin: 0;
  padding: 0;
  width: 100%;
  box-sizing: border-box;
  overflow: hidden;
}
.cf-srv-inlay-bar{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 6px 10px;
  background: rgba(79,140,255,.08);
  border: 1px solid rgba(79,140,255,.22);
  border-radius: 10px;
  box-sizing: border-box;
  overflow: hidden;
  min-height: 0;
}
.cf-srv-inlay-text{
  min-width: 0;
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.cf-srv-inlay-title{
  font-size: 12px;
  font-weight: 800;
  color: var(--cf-text,#e6edf7);
  line-height: 1.15;
}
.cf-srv-inlay-sub{
  font-size: 9px;
  line-height: 1.15;
  color: var(--cf-muted,#9db0cc);
  opacity: .92;
}
.cf-srv-inlay-status{
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  white-space: nowrap;
}
.cf-srv-inlay-st{
  font-size: 12px;
  font-weight: 800;
  color: var(--cf-text,#e6edf7);
  font-variant-numeric: tabular-nums;
}
.cf-srv-inlay-text--compact{
  gap: 0;
  justify-content: center;
}
"""


def main() -> None:
    data = json.loads(p.read_text(encoding="utf-8-sig"))
    for n in data:
        if not isinstance(n, dict):
            continue
        if n.get("id") == "ui_tpl_status_line":
            n["format"] = FMT_R4
            n["height"] = "1"
        elif n.get("id") == "ui_tpl_pi_mosq":
            n["format"] = FMT_MOSQ
            n["height"] = "1"
        elif n.get("id") == "ui_tpl_pi_nodered":
            n["format"] = FMT_NR
            n["height"] = "1"
        elif n.get("id") == "ui_tpl_tele_guard":
            n["format"] = FMT_TELE_GUARD
        elif n.get("id") == "ui_tpl_arduino_led_tele":
            fmt = n.get("format") or ""
            if "cf-tele-sum-tight" not in fmt:
                fmt = fmt.replace('<div class="cf-tele-sum-ui">', '<div class="cf-tele-sum-ui cf-tele-sum-tight">', 1)
                fmt = fmt.replace("</style>", ".cf-tele-sum-ui.cf-tele-sum-tight{margin-top:-18px!important}</style>", 1)
            else:
                fmt = re.sub(r"margin-top:-1[04]px", "margin-top:-18px", fmt)
            if fmt != (n.get("format") or ""):
                n["format"] = fmt

    for n in data:
        if isinstance(n, dict) and n.get("id") == "ui_tpl_css_tiles_v1":
            fmt = n.get("format", "")
            if OLD_TILES_R4_CSS in fmt:
                fmt = fmt.replace(OLD_TILES_R4_CSS, NEW_TILES_SRV_CSS)
            elif "/* R4 MQTT·Mosquitto:" in fmt:
                start = fmt.find("/* R4 MQTT·Mosquitto:")
                end = fmt.find("</style>", start)
                if start >= 0 and end > start:
                    fmt = fmt[:start] + NEW_TILES_SRV_CSS + fmt[end:]
            elif "cf-srv-inlay" not in fmt:
                fmt = fmt.replace("</style>", NEW_TILES_SRV_CSS + "</style>", 1)
            n["format"] = fmt
            break

    p.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("OK", p)


if __name__ == "__main__":
    main()
