# 모니터: Arduino online = tele 실수신만, Mosquitto 라벨 명확화 (일회성 패치 스크립트로 유지 가능)
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

NEW_FN = """const now=Date.now();
const ls=flow.get('arduinoLastStatusMs')||0;
const lt=flow.get('arduinoLastTeleMs')||0;
const TELE_MS=15000;
// retain status는 단절 후에도 online이 남을 수 있어 온라인 판정은 tele만 사용(펌웨어 tele 약 1Hz)
const ok = lt > 0 && (now - lt) < TELE_MS;
msg._ok=ok;
msg.statusAge=ls?Math.floor((now-ls)/1000):null;
msg.teleAge=lt?Math.floor((now-lt)/1000):null;
const pl=msg.payload;
let raw='';
if(typeof pl==='string'&&pl.length){ raw=pl; }
else { raw=(flow.get('lastTeleStr')||'').toString(); }
msg.telePreview = raw;
msg.payload = raw;
return msg;"""

NEW_STATUS_TPL = """<div class="cf-mqtt-one cf-arduino-stack-gap0 cf-row cf-row-pi-srv" style="margin:0;padding:4px 0 4px;min-height:auto;align-items:flex-start;"><div style="display:flex;flex-direction:column;gap:1px;min-width:0;"><div class="cf-label">Arduino 실시간</div><div class="cf-muted" style="font-size:10px;line-height:1.2;opacity:.85">tele 수신 기준 (~15s)</div></div><div style="display:flex;align-items:center;gap:8px;flex-shrink:0;padding-top:1px;"><div class="cf-dot" ng-class="msg._ok ? 'cf-dot-on' : 'cf-dot-off'"></div><div style="font-size:12px;color:var(--cf-text);white-space:nowrap;">{{msg._ok ? 'online' : 'offline'}}</div></div></div><style>.nr-dashboard-template:has(.cf-mqtt-one){height:auto!important;overflow:visible!important;margin:0!important;padding:0!important}</style>"""

NEW_MOSQ_TPL = """<div class="cf-row cf-row-pi-srv" style="align-items:flex-start;"><div style="display:flex;flex-direction:column;gap:1px;min-width:0;flex:1;"><div class="cf-label">Mosquitto</div><div class="cf-muted" style="font-size:10px;line-height:1.2;opacity:.85">Pi 브로커 데몬(systemd) — 아두이노 연결과 무관</div></div><div style="display:flex;align-items:center;gap:10px;flex-shrink:0;padding-top:1px;"><div class="cf-dot" ng-class="msg._ok ? 'cf-dot-on' : 'cf-dot-off'"></div><div style="font-size:12px;color:var(--cf-text);white-space:nowrap;">{{msg._ok ? 'online' : 'offline'}}</div></div></div>"""


def main() -> None:
    data = json.loads(p.read_text(encoding="utf-8-sig"))
    for n in data:
        if not isinstance(n, dict):
            continue
        if n.get("id") == "fn_calc_online":
            n["func"] = NEW_FN
            n["wires"] = [["ui_tpl_conn_line", "ui_tpl_status_line"]]
        elif n.get("id") == "ui_tpl_status_line":
            n["format"] = NEW_STATUS_TPL
        elif n.get("id") == "mqtt_in_status":
            n["wires"] = [["fn_seen_status", "ui_txt_status_raw"]]
        elif n.get("id") == "ui_tpl_pi_mosq":
            n["format"] = NEW_MOSQ_TPL
    p.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print("OK", p)


if __name__ == "__main__":
    main()
