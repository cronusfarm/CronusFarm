# 모니터: retain status 줄을 tele 기준 _ok와 동기화, KMA 관측 시각 포맷, R4/System 라벨 정리
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

FN_SEEN_STATUS = """let p = msg.payload;
if (Buffer.isBuffer(p)) p = p.toString('utf8');
else if (p != null && typeof p !== 'string') p = String(p);
else p = (p || '').toString();
flow.set('arduinoLastStatusMs', Date.now());
flow.set('lastStatusStr', p.trim());
msg.payload = p;
return msg;"""

FN_CALC_ONLINE = """const now=Date.now();
const ls=flow.get('arduinoLastStatusMs')||0;
const lt=flow.get('arduinoLastTeleMs')||0;
const TELE_MS=15000;
// retain status는 단절 후에도 online이 남을 수 있어 온라인 판정은 tele만 사용(펌웨어 tele 약 1Hz)
const ok = lt > 0 && (now - lt) < TELE_MS;
msg._ok=ok;
msg.statusAge=ls?Math.floor((now-ls)/1000):null;
msg.teleAge=lt?Math.floor((now-lt)/1000):null;
msg.statusRetain=(flow.get('lastStatusStr')||'').toString().trim();
const pl=msg.payload;
let raw='';
if(typeof pl==='string'&&pl.length){ raw=pl; }
else { raw=(flow.get('lastTeleStr')||'').toString(); }
msg.telePreview = raw;
msg.payload = raw;
return msg;"""

FN_KMA = """function fmtKmaObsLabel(o) {
  if (!o || typeof o !== 'object') return '';
  const d = String(o.base_date || '').trim();
  let t = String(o.base_time != null ? o.base_time : '').trim();
  if (d.length < 8) return '';
  if (!t) t = '0000';
  t = t.padStart(4, '0');
  const y = d.slice(0, 4);
  const mo = d.slice(4, 6);
  const da = d.slice(6, 8);
  const hh = t.slice(0, 2);
  const mm = t.slice(2, 4);
  return y + '.' + mo + '.' + da + ' ' + hh + ':' + mm + ' KST';
}
let p = msg.payload;
if (typeof p === 'string') {
  try { p = JSON.parse(p); } catch (e) { return msg; }
}
if (p && typeof p === 'object') {
  p.kma_obs_label = fmtKmaObsLabel(p);
  flow.set('kmaSnapshot', p);
  global.set('kmaSnapshot', p);
  flow.set('kmaSnapshotTs', Date.now());
  global.set('kmaSnapshotTs', Date.now());
}
msg.payload = p;
return msg;"""

FMT_CONN = """<div class="cf-arduino-conn-tile"><div class="cf-row cf-arduino-conn"><div class="cf-label">R4 연결</div><div style="display:flex;align-items:center;gap:10px;flex-shrink:0;"><div class="cf-dot" ng-class="msg._ok ? 'cf-dot-on' : 'cf-dot-off'"></div><div style="font-size:12px;color:var(--cf-text);white-space:nowrap;">{{msg._ok ? 'online' : 'offline'}} <span class="cf-muted">· tele {{msg.teleAge}}s · status 수신 {{msg.statusAge}}s</span></div></div></div><p class="cf-led-hint">내장 매트릭스: 위 = WiFi · 아래 = MQTT (메인 R4)</p></div><style>.cf-arduino-conn-tile{margin:0;padding:0;line-height:1.25}.cf-arduino-conn-tile .cf-arduino-conn{padding:0;margin:0;border-bottom:none}.cf-led-hint{margin:2px 0 0;padding:0;font-size:10px;line-height:1.3;color:var(--cf-muted,#9db0cc);opacity:.92}</style>"""

FMT_STATLINE = """<div class="cf-mqtt-one cf-arduino-stack-gap0 cf-row cf-row-pi-srv" style="margin:0;padding:4px 0 4px;min-height:auto;align-items:flex-start;"><div style="display:flex;flex-direction:column;gap:1px;min-width:0;"><div class="cf-label">R4 MQTT</div><div class="cf-muted" style="font-size:10px;line-height:1.2;opacity:.85">Pi(ida) Mosquitto 붙음 — tele 수신 시 online (~15s)</div></div><div style="display:flex;align-items:center;gap:8px;flex-shrink:0;padding-top:1px;"><div class="cf-dot" ng-class="msg._ok ? 'cf-dot-on' : 'cf-dot-off'"></div><div style="font-size:12px;color:var(--cf-text);white-space:nowrap;">{{msg._ok ? 'online' : 'offline'}}</div></div></div><style>.nr-dashboard-template:has(.cf-mqtt-one){height:auto!important;overflow:visible!important;margin:0!important;padding:0!important}</style>"""

FMT_STATUS_RAW = """<div class="cf-mqtt-unified"><div class="cf-mqtt-unified-bar"><div class="cf-dot" ng-class="msg._ok ? 'cf-dot-on' : 'cf-dot-off'"></div><span class="cf-mqtt-st">{{ msg.statusRetain || '—' }}</span><span class="cf-mqtt-hint">retain · …/status · 점=tele 기준</span></div><pre class="cf-mqtt-unified-raw" ng-if="msg.statusRetain && msg.statusRetain.length > 0 && msg.statusRetain.toLowerCase() !== 'online' && msg.statusRetain.toLowerCase() !== 'offline'">{{msg.statusRetain}}</pre></div><style>.cf-mqtt-unified{margin:0;padding:0;display:flex;flex-direction:column;gap:2px;width:100%}.cf-mqtt-unified-bar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:6px 10px;background:rgba(79,140,255,.08);border:1px solid rgba(79,140,255,.22);border-radius:10px}.cf-mqtt-st{font-size:13px;font-weight:800;color:var(--cf-text,#e6edf7)}.cf-mqtt-hint{margin-left:auto;font-size:10px;color:var(--cf-muted,#9db0cc);opacity:.85}.cf-mqtt-unified-raw{margin:0!important;padding:4px 8px!important;font-size:10px;line-height:1.35;color:#e6edf7;background:rgba(0,0,0,.2);border:1px solid rgba(255,255,255,.08);border-radius:8px;white-space:pre-wrap;word-break:break-word;max-height:5rem;overflow:auto}</style>"""

FMT_PI_MOSQ = """<div class="cf-row cf-row-pi-srv" style="align-items:flex-start;"><div style="display:flex;flex-direction:column;gap:1px;min-width:0;flex:1;"><div class="cf-label">Mosquitto</div><div class="cf-muted" style="font-size:10px;line-height:1.2;opacity:.85">Pi 로컬 브로커(systemd). R4가 붙었는지는 Arduino 카드 「R4 MQTT」 줄(tele) 참고.</div></div><div style="display:flex;align-items:center;gap:10px;flex-shrink:0;padding-top:1px;"><div class="cf-dot" ng-class="msg._ok ? 'cf-dot-on' : 'cf-dot-off'"></div><div style="font-size:12px;color:var(--cf-text);white-space:nowrap;">{{msg._ok ? 'online' : 'offline'}}</div></div></div>"""


def main() -> None:
    data = json.loads(p.read_text(encoding="utf-8-sig"))
    for n in data:
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        if nid == "fn_seen_status":
            n["func"] = FN_SEEN_STATUS
        elif nid == "fn_calc_online":
            n["func"] = FN_CALC_ONLINE
            n["wires"] = [["ui_tpl_conn_line", "ui_tpl_status_line"]]
        elif nid == "mqtt_in_status":
            n["wires"] = [["fn_seen_status"]]
        elif nid == "ui_txt_status_raw":
            n["format"] = FMT_STATUS_RAW
            n["name"] = "R4 status retain"
        elif nid == "ui_tpl_conn_line":
            n["format"] = FMT_CONN
        elif nid == "ui_tpl_status_line":
            n["format"] = FMT_STATLINE
            n["name"] = "R4 MQTT 상태"
        elif nid == "ui_tpl_pi_mosq":
            n["format"] = FMT_PI_MOSQ
        elif nid == "cf_fn_kma_cache":
            n["func"] = FN_KMA
        elif nid == "ui_tpl_farm_env":
            fmt = n.get("format") or ""
            old_sub = '<span class="cf-fe-box-sub">{{msg.payload.base_date ? (\'관측 \' + msg.payload.base_date + \' \' + (msg.payload.base_time||\'\') + \' KST\') : \'\'}}</span>'
            new_sub = '<span class="cf-fe-box-sub">{{msg.payload.kma_obs_label ? (\'관측 \' + msg.payload.kma_obs_label) : \'\'}}</span>'
            if old_sub in fmt:
                n["format"] = fmt.replace(old_sub, new_sub)
            else:
                raise SystemExit("ui_tpl_farm_env: expected KMA sub span not found")

    p.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("OK", p)


if __name__ == "__main__":
    main()
