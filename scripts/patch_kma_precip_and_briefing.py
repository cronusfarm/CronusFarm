# -*- coding: utf-8 -*-
"""KMA 스냅샷·모니터 UI·텔레그램 저녁 브리핑에 강수형태·1시간 강수 반영."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FN_KMA_TO_INFLUX = r"""// KMA 응답(JSON) → Influx write + MQTT 스냅샷(/ui Farm 환경)
// 출력1: Influx(토큰 있을 때만) · 출력2: cronusfarm/kma/snapshot(retain)

const token = (env.get('CRONUSFARM_INFLUX_TOKEN') || '').toString().trim();

function numOrNull(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

if (typeof msg.payload === 'string') {
  const raw = msg.payload;
  try {
    msg.payload = JSON.parse(raw);
  } catch (e) {
    node.warn('KMA: JSON 파싱 실패(응답 일부): ' + raw.slice(0, 200));
    return null;
  }
}

const body = msg.payload;
const items = body?.response?.body?.items?.item;
if (!Array.isArray(items)) {
  node.warn('KMA: items 없음/형식 불일치');
  return null;
}

const m = {};
for (const it of items) {
  const cat = (it?.category || '').toString();
  const val = (it?.obsrValue ?? '').toString();
  if (!cat) continue;
  m[cat] = val;
}

const temp = numOrNull(m.T1H);
const reh = numOrNull(m.REH);
const vec = numOrNull(m.VEC);
const wsd = numOrNull(m.WSD);
const pty = numOrNull(m.PTY);
const rn1 = numOrNull(m.RN1);

const fields = [];
if (temp !== null) fields.push(`kma_temp=${temp}`);
if (reh !== null) fields.push(`kma_humidity=${reh}`);
if (vec !== null) fields.push(`kma_wind_dir=${vec}`);
if (wsd !== null) fields.push(`kma_wind_speed=${wsd}`);
if (pty !== null) fields.push(`kma_pty=${pty}i`);
if (rn1 !== null) fields.push(`kma_precip_1h=${rn1}`);

const now = Date.now();
const org = encodeURIComponent(((env.get('CRONUSFARM_INFLUX_ORG') || 'cronusfarm').toString()));
const bucket = encodeURIComponent(((env.get('CRONUSFARM_INFLUX_BUCKET') || 'CronusFarm').toString()));
const base = ((env.get('CRONUSFARM_INFLUX_URL') || 'http://127.0.0.1:8086/api/v2/write').toString()).replace(/\/$/, '');
const nx = msg.kma?.nx;
const ny = msg.kma?.ny;
const tags = [`source=kma`];
if (nx && ny) tags.push(`nx=${nx}`, `ny=${ny}`);

const snap = {
  kma_temp: temp,
  kma_humidity: reh,
  kma_wind_dir: vec,
  kma_wind_speed: wsd,
  kma_pty: pty,
  kma_precip_type: pty,
  kma_precip_1h: rn1,
  base_date: msg.kma?.base_date,
  base_time: msg.kma?.base_time,
  nx,
  ny,
  ts: now
};

const uiMsg = {
  topic: 'cronusfarm/kma/snapshot',
  qos: 0,
  retain: true,
  payload: JSON.stringify(snap)
};

let influxMsg = null;
if (token && fields.length) {
  influxMsg = {
    method: 'POST',
    url: `${base}?org=${org}&bucket=${bucket}&precision=ns`,
    headers: { Authorization: `Token ${token}`, 'Content-Type': 'text/plain; charset=utf-8' },
    payload: `tele,${tags.join(',')} ${fields.join(',')} ${now * 1e6}`
  };
}

return [ influxMsg, uiMsg ];"""

FN_KMA_CACHE = r"""function fmtKmaObsLabel(o) {
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
function kmaPtyLabel(v, rn1) {
  if (v === null || v === undefined || v === '') v = '';
  const m = { '0': '없음', '1': '비', '2': '비/눈', '3': '눈', '4': '소나기', '5': '빗방울', '6': '빗방울눈날림', '7': '눈날림' };
  let label = (v === '' || v == null) ? '—' : (m[String(v)] || String(v));
  const r = Number(rn1);
  if ((label === '없음' || label === '—') && Number.isFinite(r) && r > 0) label = '강우';
  return label;
}
let p = msg.payload;
if (typeof p === 'string') {
  try { p = JSON.parse(p); } catch (e) { return msg; }
}
if (p && typeof p === 'object') {
  if (p.kma_precip_type == null && p.kma_pty != null) p.kma_precip_type = p.kma_pty;
  if (p.kma_precip_1h == null && p.kma_rn1 != null) p.kma_precip_1h = p.kma_rn1;
  p.kma_precip_type_label = kmaPtyLabel(p.kma_precip_type, p.kma_precip_1h);
  p.kma_obs_label = fmtKmaObsLabel(p);
  flow.set('kmaSnapshot', p);
  global.set('kmaSnapshot', p);
  flow.set('kmaSnapshotTs', Date.now());
  global.set('kmaSnapshotTs', Date.now());
}
msg.payload = p;
return msg;"""

FN_NEWS_EVENING = r"""const token = (env.get('CRONUSFARM_TELEGRAM_BOT_TOKEN') || '').toString().trim();
const chat = (env.get('CRONUSFARM_TELEGRAM_CHAT_ID') || '').toString().trim();
if (!token || !chat) { return null; }

function fmtKst(ms) {
  if (!ms) return '미수신';
  const d = new Date(Number(ms) + 9 * 60 * 60 * 1000);
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(d.getUTCDate()).padStart(2, '0');
  const hh = String(d.getUTCHours()).padStart(2, '0');
  const mm = String(d.getUTCMinutes()).padStart(2, '0');
  const ss = String(d.getUTCSeconds()).padStart(2, '0');
  return `${y}-${m}-${dd} ${hh}:${mm}:${ss} KST`;
}
function kmaPtyLabel(v) {
  if (v === '' || v == null) return '미수신';
  const m = { '0': '없음', '1': '비', '2': '비/눈', '3': '눈', '4': '소나기', '5': '빗방울', '6': '빗방울눈날림', '7': '눈날림' };
  return m[String(v)] || String(v);
}

const now = new Date(Date.now() + 9 * 60 * 60 * 1000);
const mon = String(now.getUTCMonth() + 1).padStart(2, '0');
const day = String(now.getUTCDate()).padStart(2, '0');

const teleTs = fmtKst(flow.get('arduinoLastTeleMs'));
const statusTs = fmtKst(flow.get('arduinoLastStatusMs'));
const gState = (flow.get('lastTeleG') || '').toString().trim() || '미수신';
const lastTele = (flow.get('lastTeleStr') || '').toString().trim();
const telePreview = lastTele ? lastTele.slice(0, 120) : '미수신';

const kma = flow.get('kmaSnapshot') || global.get('kmaSnapshot') || {};
const kmaTs = flow.get('kmaSnapshotTs') || global.get('kmaSnapshotTs') || null;
const temp = (kma.kma_temp ?? '미수신');
const hum = (kma.kma_humidity ?? '미수신');
const ptyRaw = (kma.kma_precip_type ?? kma.kma_pty ?? '');
const pcp = (kma.kma_precip_1h ?? '미수신');
const ptyMap = { '0': '없음', '1': '비', '2': '비/눈', '3': '눈', '4': '소나기' };
let pty = (ptyRaw === '' || ptyRaw == null) ? '미수신' : (ptyMap[String(ptyRaw)] || String(ptyRaw));
const rn1n = Number(pcp);
if ((pty === '없음' || pty === '미수신') && Number.isFinite(rn1n) && rn1n > 0) pty = '강우';

const ai = flow.get('cameraAiSnapshot') || global.get('cameraAiSnapshot') || {};
const aiCount = (ai.count != null) ? ai.count : '미수신';
const aiCap = (ai.caption || '').toString().trim() || '미수신';

const phw = flow.get('phwSnapshot') || global.get('phwSnapshot') || {};
function phwFmt(v) {
  if (v == null || v === '') return '미수신';
  const n = Number(v);
  return Number.isFinite(n) ? String(Math.round(n * 100) / 100) : String(v);
}
const ph = phwFmt(phw.ph);
const ec = phwFmt(phw.ec);
const wtemp = phwFmt(phw.temp_c);

const text =
`🌙 ${mon}월 ${day}일 저녁 영농 준비

🌤️ 날씨(KMA): 🌡️ ${temp}${temp === '미수신' ? '' : '°C'}  |  💧 ${hum}${hum === '미수신' ? '' : '%'}  |  🌧️ ${pty}  |  ☔ 1h ${pcp}${pcp === '미수신' ? '' : 'mm'}
🛰️ 관측: ${fmtKst(kmaTs)}

📡 MQTT
• tele: ${teleTs}
• status: ${statusTs}
• 펌프가드(G): ${gState}
• tele: ${telePreview}

🧪 PHW3988(센서): pH ${ph}  |  EC ${ec} µS/cm  |  수온 ${wtemp}${wtemp === '미수신' ? '' : '°C'}

📷 CCTV AI: ${aiCount}개 — ${aiCap}

📋 점검
• tele/status·펌프가드(G) 지속 수신 확인
• 스케줄/수동(auto_*) 값 의도 유지 여부`;

msg.method = 'POST';
msg.url = 'https://api.telegram.org/bot' + token + '/sendMessage';
msg.headers = { 'Content-Type': 'application/json; charset=utf-8' };
msg.payload = JSON.stringify({ chat_id: Number(chat), text: text });
return msg;"""

KMA_UI_EXTRA = """          <span class="k">강수형태</span><span class="v">{{msg.payload.kma_precip_type_label || '—'}}</span>
          <span class="k">1시간 강수</span><span class="v">{{(msg.payload.kma_precip_1h != null && msg.payload.kma_precip_1h !== '') ? (msg.payload.kma_precip_1h + ' mm') : '—'}}</span>
"""

PHW_UI = """      <div class="cf-fe-box">
        <div class="cf-fe-box-title">배양액 PHW3988</div>
        <div class="cf-fe-box-rule"></div>
        <div class="cf-fe-kv">
          <span class="k">pH</span><span class="v">{{(msg.payload.ph != null && msg.payload.ph !== '') ? msg.payload.ph : '—'}}</span>
          <span class="k">EC</span><span class="v">{{(msg.payload.ec != null && msg.payload.ec !== '') ? msg.payload.ec : '—'}}</span>
          <span class="k">수온</span><span class="v">{{(msg.payload.temp_c != null && msg.payload.temp_c !== '') ? (msg.payload.temp_c + ' °C') : '—'}}</span>
        </div>
      </div>

      <div class="cf-fe-box">
        <div class="cf-fe-box-title">CCTV AI</div>
        <div class="cf-fe-box-rule"></div>
        <div class="cf-fe-kv cf-fe-kv-one">
          <span class="k">검출</span><span class="v">{{msg.payload.ai_caption || ((msg.payload.ai_count != null) ? (msg.payload.ai_count + '개') : '—')}}</span>
        </div>
      </div>
"""

FN_PHW_CACHE = r"""let p = msg.payload;
if (typeof p === 'string') {
  try { p = JSON.parse(p); } catch (e) { return msg; }
}
if (p && typeof p === 'object' && p.ok) {
  flow.set('phwSnapshot', p);
  global.set('phwSnapshot', p);
}
msg.payload = p;
return msg;"""

FN_AI_CACHE = r"""let p = msg.payload;
if (typeof p === 'string') {
  try { p = JSON.parse(p); } catch (e) { return msg; }
}
if (p && typeof p === 'object') {
  flow.set('cameraAiSnapshot', p);
  global.set('cameraAiSnapshot', p);
}
msg.payload = p;
return msg;"""

FN_FARM_ENV_MERGE = r"""const kma = flow.get('kmaSnapshot') || global.get('kmaSnapshot') || {};
const phw = flow.get('phwSnapshot') || global.get('phwSnapshot') || {};
const ai = flow.get('cameraAiSnapshot') || global.get('cameraAiSnapshot') || {};
msg.payload = Object.assign({}, kma, {
  ph: phw.ph,
  ec: phw.ec,
  temp_c: phw.temp_c,
  ai_count: ai.count,
  ai_caption: ai.caption
});
return msg;"""


def patch_flow(path: Path) -> None:
    if not path.is_file():
        return
    flows = json.loads(path.read_text(encoding="utf-8-sig"))
    ids = {n.get("id") for n in flows if isinstance(n, dict)}
    changed = []

    for n in flows:
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        if nid == "fn_kma_to_influx":
            n["func"] = FN_KMA_TO_INFLUX
            changed.append("fn_kma_to_influx")
        elif nid == "cf_fn_kma_cache":
            n["func"] = FN_KMA_CACHE
            changed.append("cf_fn_kma_cache")
        elif nid == "cf_fn_tg_news_daily":
            n["func"] = FN_NEWS_EVENING
            changed.append("cf_fn_tg_news_daily")
        elif nid == "ui_tpl_farm_env":
            fmt = n.get("format") or ""
            if "강수형태" not in fmt and "kma_wind_speed" in fmt:
                fmt = fmt.replace(
                    '<span class="k">풍속</span><span class="v">{{(msg.payload.kma_wind_speed != null && msg.payload.kma_wind_speed !== \'\') ? (msg.payload.kma_wind_speed + \' m/s\') : \'—\'}}</span>\n        </div>',
                    '<span class="k">풍속</span><span class="v">{{(msg.payload.kma_wind_speed != null && msg.payload.kma_wind_speed !== \'\') ? (msg.payload.kma_wind_speed + \' m/s\') : \'—\'}}</span>\n'
                    + KMA_UI_EXTRA
                    + "        </div>",
                )
            if "PHW3988" not in fmt and "cf-fe-grid" in fmt:
                fmt = fmt.replace(
                    '      <div class="cf-fe-box">\n        <div class="cf-fe-box-title">온실</div>',
                    PHW_UI
                    + '      <div class="cf-fe-box">\n        <div class="cf-fe-box-title">온실</div>',
                )
                fmt = re.sub(
                    r"grid-template-columns:\s*1fr 1fr",
                    "grid-template-columns: repeat(auto-fit, minmax(200px, 1fr))",
                    fmt,
                    count=1,
                )
            n["format"] = fmt
            changed.append("ui_tpl_farm_env")

    # 저녁 17:00 inject
    if "cf_inj_tg_news_evening" not in ids:
        tab = "b1c5a1f1d7a2a3a1"
        for n in flows:
            if n.get("id") == "cf_inj_tg_news_daily":
                tab = n.get("z", tab)
                break
        flows.append(
            {
                "id": "cf_inj_tg_news_evening",
                "type": "inject",
                "z": tab,
                "name": "텔레그램 뉴스(매일 17:00)",
                "props": [{"p": "payload"}],
                "repeat": "",
                "crontab": "0 17 * * *",
                "once": False,
                "onceDelay": 0.1,
                "topic": "",
                "payload": "",
                "payloadType": "date",
                "x": 210,
                "y": 1580,
                "wires": [["cf_fn_tg_news_daily"]],
            }
        )
        changed.append("cf_inj_tg_news_evening")

    # PHW / AI cache nodes + farm env merge tick
    tab_dash = "tab_cronus_dash"
    for n in flows:
        if n.get("id") == "mqtt_in_kma_snap":
            tab_dash = n.get("z", tab_dash)
            break

    if "cf_fn_phw_cache" not in ids:
        flows.append(
            {
                "id": "inj_phw_poll",
                "type": "inject",
                "z": tab_dash,
                "name": "PHW poll 60s",
                "props": [{"p": "payload"}],
                "repeat": "60",
                "crontab": "",
                "once": True,
                "onceDelay": 2,
                "topic": "",
                "payload": "",
                "payloadType": "date",
                "x": 120,
                "y": 1180,
                "wires": [["cf_fn_phw_fetch"]],
            }
        )
        flows.append(
            {
                "id": "cf_fn_phw_fetch",
                "type": "function",
                "z": tab_dash,
                "name": "PHW latest URL",
                "func": "const base = (env.get('CRONUSFARM_SQLITE_BRIDGE_URL') || 'http://127.0.0.1:18766').toString().replace(/\\/$/, '');\nmsg.method = 'GET';\nmsg.url = base + '/api/sensor/latest?device_id=cronusfarm-01&zone=phw3988';\nreturn msg;",
                "outputs": 1,
                "timeout": 0,
                "noerr": 0,
                "initialize": "",
                "finalize": "",
                "libs": [],
                "x": 320,
                "y": 1180,
                "wires": [["cf_hreq_phw_latest"]],
            }
        )
        flows.append(
            {
                "id": "cf_hreq_phw_latest",
                "type": "http request",
                "z": tab_dash,
                "name": "bridge PHW",
                "method": "use",
                "ret": "txt",
                "paytoqs": "ignore",
                "url": "",
                "tls": "",
                "persist": False,
                "proxy": "",
                "authType": "",
                "senderr": False,
                "headers": [],
                "x": 520,
                "y": 1180,
                "wires": [["cf_fn_phw_cache", "cf_fn_farm_env_merge"]],
            }
        )
        flows.append(
            {
                "id": "cf_fn_phw_cache",
                "type": "function",
                "z": tab_dash,
                "name": "PHW snapshot cache",
                "func": FN_PHW_CACHE,
                "outputs": 1,
                "timeout": 0,
                "noerr": 0,
                "initialize": "",
                "finalize": "",
                "libs": [],
                "x": 720,
                "y": 1160,
                "wires": [[]],
            }
        )
        changed.append("phw_poll")

    if "cf_fn_ai_cache" not in ids:
        flows.append(
            {
                "id": "mqtt_in_camera_ai",
                "type": "mqtt in",
                "z": tab_dash,
                "name": "camera ai_count",
                "topic": "cronusfarm/camera/ai_count",
                "qos": "0",
                "datatype": "json",
                "broker": "d6b7f6c1b2b3c4d5",
                "nl": False,
                "rap": True,
                "rh": 0,
                "inputs": 0,
                "x": 150,
                "y": 1220,
                "wires": [["cf_fn_ai_cache", "cf_fn_farm_env_merge"]],
            }
        )
        flows.append(
            {
                "id": "cf_fn_ai_cache",
                "type": "function",
                "z": tab_dash,
                "name": "CCTV AI cache",
                "func": FN_AI_CACHE,
                "outputs": 1,
                "timeout": 0,
                "noerr": 0,
                "initialize": "",
                "finalize": "",
                "libs": [],
                "x": 380,
                "y": 1220,
                "wires": [[]],
            }
        )
        changed.append("ai_cache")

    if "cf_fn_farm_env_merge" not in ids:
        flows.append(
            {
                "id": "inj_farm_env_merge",
                "type": "inject",
                "z": tab_dash,
                "name": "farm env merge 15s",
                "props": [{"p": "payload"}],
                "repeat": "15",
                "crontab": "",
                "once": True,
                "onceDelay": 1,
                "topic": "",
                "payload": "",
                "payloadType": "date",
                "x": 140,
                "y": 1260,
                "wires": [["cf_fn_farm_env_merge"]],
            }
        )
        flows.append(
            {
                "id": "cf_fn_farm_env_merge",
                "type": "function",
                "z": tab_dash,
                "name": "farm env merge",
                "func": FN_FARM_ENV_MERGE,
                "outputs": 1,
                "timeout": 0,
                "noerr": 0,
                "initialize": "",
                "finalize": "",
                "libs": [],
                "x": 360,
                "y": 1260,
                "wires": [["ui_tpl_farm_env"]],
            }
        )
        changed.append("farm_env_merge")

    # KMA → cache + merge (not direct ui_tpl)
    for n in flows:
        if n.get("id") == "mqtt_in_kma_snap":
            w = n.get("wires", [[]])
            outs = w[0] if w else []
            if "cf_fn_kma_cache" not in outs:
                outs = ["cf_fn_kma_cache"] + [x for x in outs if x != "ui_tpl_farm_env"]
            if "cf_fn_farm_env_merge" not in outs:
                outs.append("cf_fn_farm_env_merge")
            n["wires"] = [outs]
            changed.append("mqtt_in_kma_snap_wire")

    path.write_text(json.dumps(flows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"OK {path.name}: {', '.join(changed) or 'no changes'}")


def main() -> None:
    for name in (
        "flows_cronusfarm_dashboard.json",
        "flows_cronusfarm_mqtt.json",
        "CronusFarm_NodeRED_flow.json",
    ):
        patch_flow(ROOT / "nodered" / name)


if __name__ == "__main__":
    main()
