# one-off / 유지: flows_cronusfarm_mqtt.json Influx·SQLite 연동 패치
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
p = root / "nodered" / "flows_cronusfarm_mqtt.json"
data = json.loads(p.read_text(encoding="utf-8-sig"))

NEW_FUNC = r"""// MQTT tele → InfluxDB 2.x Line Protocol (측정값만, 토큰은 환경변수)
// 채널·펌프가드(G:)·fan·pump_c/d 포함
// 필요: CRONUSFARM_INFLUX_TOKEN, 선택: CRONUSFARM_INFLUX_ORG, CRONUSFARM_INFLUX_BUCKET, CRONUSFARM_INFLUX_MIN_MS

const token = (env.get('CRONUSFARM_INFLUX_TOKEN') || '').toString().trim();
if (!token) {
  if (!flow.get('_influxWarned')) {
    flow.set('_influxWarned', true);
    node.warn('Influx: CRONUSFARM_INFLUX_TOKEN 없음 → 기록 생략');
  }
  return null;
}

const minMs = parseInt((env.get('CRONUSFARM_INFLUX_MIN_MS') || '5000').toString(), 10) || 5000;
const now = Date.now();
const last = flow.get('lastInfluxWriteMs') || 0;
if (now - last < minMs) return null;
flow.set('lastInfluxWriteMs', now);

const s = (msg.payload || '').toString();
if (!s.trim()) return null;

function parseKV(part) {
  const out = {};
  (part || '').trim().split(/\s+/).forEach(tok => {
    const m = tok.match(/^([^=]+)=(.+)$/);
    if (!m) return;
    out[m[1]] = m[2];
  });
  return out;
}

const ps = s.split('|').map(x => x.trim());
const pS = ps.find(x => x.startsWith('S:'));
const pA = ps.find(x => x.startsWith('A:'));
const pT = ps.find(x => x.startsWith('T:'));
const kvS = parseKV(pS ? pS.slice(2) : '');
const kvA = parseKV(pA ? pA.slice(2) : '');
const kvT = parseKV(pT ? pT.slice(2) : '');
const pG = ps.find(x => x.startsWith('G:'));
let guard_ok = 1, guard_mx = 0, guard_mf = 0;
if (pG) {
  const gr = pG.slice(2).trim();
  if (gr && gr !== 'ok') {
    guard_ok = 0;
    gr.split(/\s+/).forEach(tok => {
      if (tok.indexOf('=mx') >= 0) guard_mx = 1;
      if (tok.indexOf('=mf') >= 0) guard_mf = 1;
    });
  }
}

const parts = (msg.topic || '').toString().split('/').filter(Boolean);
const deviceId = (parts.length >= 2 ? parts[1] : 'cronusfarm-01').replace(/[^a-zA-Z0-9_-]/g, '_');

const fields = [];
const ch = ['led_a1', 'led_a2', 'led_b1', 'led_b2', 'pump_a1', 'pump_a2', 'pump_b1', 'pump_b2', 'fan_a1', 'fan_a2', 'fan_b1', 'fan_b2', 'pump_c1', 'pump_c2', 'pump_d1', 'pump_d2'];
ch.forEach(k => {
  if (kvS[k] === undefined) return;
  fields.push(`${k}=${kvS[k] === '1' ? 1 : 0}i`);
});
ch.forEach(k => {
  if (kvA[k] === undefined) return;
  fields.push(`auto_${k}=${kvA[k] === '1' ? 1 : 0}i`);
});
Object.keys(kvT).forEach(k => {
  const m = (kvT[k] || '').toString().match(/^(\d+)\/(\d+)$/);
  if (!m) return;
  fields.push(`${k}_on_s=${parseInt(m[1], 10)}i`);
  fields.push(`${k}_off_s=${parseInt(m[2], 10)}i`);
});
fields.push(`guard_ok=${guard_ok}i`);
fields.push(`guard_mx=${guard_mx}i`);
fields.push(`guard_mf=${guard_mf}i`);

const org = encodeURIComponent(((env.get('CRONUSFARM_INFLUX_ORG') || 'cronusfarm').toString()));
const bucket = encodeURIComponent(((env.get('CRONUSFARM_INFLUX_BUCKET') || 'cronusfarm').toString()));
const base = ((env.get('CRONUSFARM_INFLUX_URL') || 'http://127.0.0.1:8086/api/v2/write').toString()).replace(/\/$/, '');

msg.method = 'POST';
msg.url = `${base}?org=${org}&bucket=${bucket}&precision=ns`;
msg.headers = {
  Authorization: `Token ${token}`,
  'Content-Type': 'text/plain; charset=utf-8'
};
msg.payload = `tele,device_id=${deviceId} ${fields.join(',')} ${now * 1e6}`;
return msg;"""

for n in data:
    if isinstance(n, dict) and n.get("id") == "f1a2b3c4d5e6f708":
        n["func"] = NEW_FUNC
        break
else:
    raise SystemExit("f1a2b3c4d5e6f708 not found")

for n in data:
    if isinstance(n, dict) and n.get("id") == "d1e4c46e7a9c11a1":
        n["topic"] = "cronusfarm/+/tele"
        w = n.setdefault("wires", [[]])[0]
        if "sq_fn_tele_sqlite" not in w:
            w.append("sq_fn_tele_sqlite")
        break
else:
    raise SystemExit("d1e4c46e7a9c11a1 not found")

extra = [
    {
        "id": "sq_fn_tele_sqlite",
        "type": "function",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "tele→SQLite 브리지",
        "func": r"""const dis = (env.get('CRONUSFARM_SQLITE_DISABLE') || '').toString().trim();
if (dis === '1' || dis.toLowerCase() === 'true') return null;
const base = (env.get('CRONUSFARM_SQLITE_BRIDGE_URL') || 'http://127.0.0.1:18766').toString().replace(/\/$/, '');
const minMs = parseInt((env.get('CRONUSFARM_SQLITE_MIN_MS') || '15000').toString(), 10) || 15000;
const now = Date.now();
const last = flow.get('lastSqliteTeleMs') || 0;
if (now - last < minMs) return null;
flow.set('lastSqliteTeleMs', now);
const parts = (msg.topic || '').toString().split('/').filter(Boolean);
const deviceId = (parts.length >= 2 ? parts[1] : 'cronusfarm-01');
msg.method = 'POST';
msg.url = base + '/ingest/tele';
msg.headers = { 'Content-Type': 'application/json; charset=utf-8' };
msg.payload = JSON.stringify({
  device_id: deviceId,
  topic: msg.topic,
  raw: (msg.payload || '').toString(),
  ts_ms: now
});
return msg;""",
        "outputs": 1,
        "noerr": 0,
        "initialize": "",
        "finalize": "",
        "libs": [],
        "x": 390,
        "y": 380,
        "wires": [["sq_http_sqlite_tele"]],
    },
    {
        "id": "sq_http_sqlite_tele",
        "type": "http request",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "SQLite HTTP tele",
        "method": "use",
        "ret": "txt",
        "paytoqs": "ignore",
        "url": "",
        "tls": "",
        "persist": False,
        "proxy": "",
        "insecureHTTPParser": False,
        "authType": "",
        "senderr": False,
        "headers": [],
        "x": 610,
        "y": 380,
        "wires": [[]],
    },
    {
        "id": "sq_mqtt_in_cmd",
        "type": "mqtt in",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "cmd 가입(기록)",
        "topic": "cronusfarm/+/cmd",
        "qos": "1",
        "datatype": "utf8",
        "broker": "d6b7f6c1b2b3c4d5",
        "nl": False,
        "rap": True,
        "rh": 0,
        "inputs": 0,
        "x": 150,
        "y": 340,
        "wires": [["sq_fn_cmd_sqlite"]],
    },
    {
        "id": "sq_fn_cmd_sqlite",
        "type": "function",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "cmd→SQLite 브리지",
        "func": r"""const dis = (env.get('CRONUSFARM_SQLITE_DISABLE') || '').toString().trim();
if (dis === '1' || dis.toLowerCase() === 'true') return null;
const base = (env.get('CRONUSFARM_SQLITE_BRIDGE_URL') || 'http://127.0.0.1:18766').toString().replace(/\/$/, '');
const parts = (msg.topic || '').toString().split('/').filter(Boolean);
const deviceId = (parts.length >= 2 ? parts[1] : 'cronusfarm-01');
const now = Date.now();
msg.method = 'POST';
msg.url = base + '/ingest/cmd';
msg.headers = { 'Content-Type': 'application/json; charset=utf-8' };
msg.payload = JSON.stringify({
  device_id: deviceId,
  topic: msg.topic,
  payload: (msg.payload || '').toString(),
  ts_ms: now
});
return msg;""",
        "outputs": 1,
        "noerr": 0,
        "initialize": "",
        "finalize": "",
        "libs": [],
        "x": 390,
        "y": 340,
        "wires": [["sq_http_sqlite_cmd"]],
    },
    {
        "id": "sq_http_sqlite_cmd",
        "type": "http request",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "SQLite HTTP cmd",
        "method": "use",
        "ret": "txt",
        "paytoqs": "ignore",
        "url": "",
        "tls": "",
        "persist": False,
        "proxy": "",
        "insecureHTTPParser": False,
        "authType": "",
        "senderr": False,
        "headers": [],
        "x": 610,
        "y": 340,
        "wires": [[]],
    },
    {
        "id": "sq_mqtt_in_status",
        "type": "mqtt in",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "status 가입(기록)",
        "topic": "cronusfarm/+/status",
        "qos": "1",
        "datatype": "utf8",
        "broker": "d6b7f6c1b2b3c4d5",
        "nl": False,
        "rap": True,
        "rh": 0,
        "inputs": 0,
        "x": 150,
        "y": 420,
        "wires": [["sq_fn_status_sqlite"]],
    },
    {
        "id": "sq_fn_status_sqlite",
        "type": "function",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "status→SQLite 브리지",
        "func": r"""const dis = (env.get('CRONUSFARM_SQLITE_DISABLE') || '').toString().trim();
if (dis === '1' || dis.toLowerCase() === 'true') return null;
const base = (env.get('CRONUSFARM_SQLITE_BRIDGE_URL') || 'http://127.0.0.1:18766').toString().replace(/\/$/, '');
const minMs = parseInt((env.get('CRONUSFARM_SQLITE_STATUS_MIN_MS') || '60000').toString(), 10) || 60000;
const now = Date.now();
const last = flow.get('lastSqliteStatusMs') || 0;
if (now - last < minMs) return null;
flow.set('lastSqliteStatusMs', now);
const parts = (msg.topic || '').toString().split('/').filter(Boolean);
const deviceId = (parts.length >= 2 ? parts[1] : 'cronusfarm-01');
msg.method = 'POST';
msg.url = base + '/ingest/status';
msg.headers = { 'Content-Type': 'application/json; charset=utf-8' };
msg.payload = JSON.stringify({
  device_id: deviceId,
  topic: msg.topic,
  payload: (msg.payload || '').toString(),
  ts_ms: now
});
return msg;""",
        "outputs": 1,
        "noerr": 0,
        "initialize": "",
        "finalize": "",
        "libs": [],
        "x": 390,
        "y": 420,
        "wires": [["sq_http_sqlite_status"]],
    },
    {
        "id": "sq_http_sqlite_status",
        "type": "http request",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "SQLite HTTP status",
        "method": "use",
        "ret": "txt",
        "paytoqs": "ignore",
        "url": "",
        "tls": "",
        "persist": False,
        "proxy": "",
        "insecureHTTPParser": False,
        "authType": "",
        "senderr": False,
        "headers": [],
        "x": 610,
        "y": 420,
        "wires": [[]],
    },
]

ids = {n.get("id") for n in data if isinstance(n, dict)}
for e in extra:
    if e["id"] not in ids:
        data.append(e)

p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
print("OK patch mqtt:", p, "nodes=", len(data))
