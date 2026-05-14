# SQLite 채널 타임라인·상태 GET 프록시 + POST channel-action(MQTT·manual_event)
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MQTT = ROOT / "nodered" / "flows_cronusfarm_mqtt.json"

CFN_CH_ACT = r"""const base = (env.get('CRONUSFARM_SQLITE_BRIDGE_URL') || 'http://127.0.0.1:18766').toString().replace(/\/$/, '');
let body = msg.payload;
if (typeof body === 'string') {
  try { body = JSON.parse(body); } catch (e) { body = {}; }
}
if (!body || typeof body !== 'object') body = {};
const devId = (body.device_id || 'cronusfarm-01').toString().trim();
const ch = (body.channel || '').toString().trim();
const action = (body.action || '').toString().trim();
const holdMin = parseInt(body.hold_minutes, 10) || 0;
const topic = 'cronusfarm/' + devId + '/cmd';
const autoKey = 'auto_' + ch;
if (!ch) {
  return [null, null, Object.assign({}, msg, {
    statusCode: 400,
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
    payload: JSON.stringify({ ok: false, error: 'channel required' })
  })];
}
function mq(pl) {
  return { topic, payload: pl, qos: 0, retain: false };
}
let cmdParts = [];
const log = {
  device_id: devId,
  channel_key: ch,
  action,
  ts_ms: Date.now(),
  mqtt_payload: '',
  prev_auto: body.prev_auto,
  new_auto: body.new_auto,
  prev_state: body.prev_state,
  new_state: body.new_state
};
const holdTKey = '_cfHoldT_' + devId + '_' + ch;
if (action === 'set_auto' || action === 'set_manual') {
  const prevT = flow.get(holdTKey);
  if (prevT) { try { clearTimeout(prevT); } catch (e) {} }
  flow.set(holdTKey, null);
}
if (action === 'set_output') {
  const on = body.on === true || body.on === 1 || body.on === '1';
  cmdParts.push(autoKey + '=0');
  cmdParts.push(ch + '=' + (on ? '1' : '0'));
} else if (action === 'set_auto') {
  cmdParts.push(autoKey + '=1');
} else if (action === 'set_manual') {
  cmdParts.push(autoKey + '=0');
  if (holdMin >= 1 && holdMin <= 60) log.hold_minutes = holdMin;
} else {
  return [null, null, Object.assign({}, msg, {
    statusCode: 400,
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
    payload: JSON.stringify({ ok: false, error: 'unknown action' })
  })];
}
const combined = cmdParts.join(' ');
log.mqtt_payload = combined;
const mqttMsg = mq(combined);
const logMsg = {
  method: 'POST',
  url: base + '/ingest/manual_event',
  headers: { 'Content-Type': 'application/json; charset=utf-8' },
  payload: JSON.stringify(log)
};
if (action === 'set_manual' && holdMin >= 1 && holdMin <= 60) {
  const ms = holdMin * 60 * 1000;
  const rev = autoKey + '=1';
  const logRev = {
    method: 'POST',
    url: base + '/ingest/manual_event',
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
    payload: JSON.stringify({
      device_id: devId,
      channel_key: ch,
      action: 'revert_auto',
      ts_ms: Date.now(),
      prev_auto: 0,
      new_auto: 1,
      mqtt_payload: rev
    })
  };
  const tid = setTimeout(() => {
    flow.set(holdTKey, null);
    node.send([mq(rev), logRev, null]);
  }, ms);
  flow.set(holdTKey, tid);
}
const resMsg = Object.assign({}, msg, {
  statusCode: 200,
  headers: { 'Content-Type': 'application/json; charset=utf-8' },
  payload: JSON.stringify({ ok: true, mqtt: combined })
});
node.send([mqttMsg, logMsg, resMsg]);
return null;"""

NEW_NODES = [
    {
        "id": "cf_hin_ch_tl",
        "type": "http in",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "채널 타임라인 GET",
        "url": "/farm/cronusfarm-sqlite/api/channel/timeline",
        "method": "get",
        "upload": False,
        "swaggerDoc": "",
        "x": 190,
        "y": 680,
        "wires": [["cf_fn_ch_tl"]],
    },
    {
        "id": "cf_fn_ch_tl",
        "type": "function",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "→ bridge timeline",
        "func": "const base = (env.get('CRONUSFARM_SQLITE_BRIDGE_URL') || 'http://127.0.0.1:18766').toString().replace(/\\/$/, '');\nconst u = (msg.req && msg.req.url) ? msg.req.url : '';\nconst q = u.indexOf('?') >= 0 ? u.slice(u.indexOf('?')) : '';\nmsg.method = 'GET';\nmsg.url = base + '/api/channel/timeline' + q;\nreturn msg;",
        "outputs": 1,
        "noerr": 0,
        "initialize": "",
        "finalize": "",
        "libs": [],
        "x": 440,
        "y": 680,
        "wires": [["cf_hreq_ch_tl"]],
    },
    {
        "id": "cf_hreq_ch_tl",
        "type": "http request",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "bridge timeline",
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
        "x": 700,
        "y": 680,
        "wires": [["cf_hres_ch_tl"]],
    },
    {
        "id": "cf_hres_ch_tl",
        "type": "http response",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "타임라인 응답",
        "statusCode": "",
        "headers": {},
        "x": 930,
        "y": 680,
        "wires": [],
    },
    {
        "id": "cf_hin_ch_st",
        "type": "http in",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "채널 상태 GET",
        "url": "/farm/cronusfarm-sqlite/api/channel/status",
        "method": "get",
        "upload": False,
        "swaggerDoc": "",
        "x": 190,
        "y": 720,
        "wires": [["cf_fn_ch_st"]],
    },
    {
        "id": "cf_fn_ch_st",
        "type": "function",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "→ bridge status",
        "func": "const base = (env.get('CRONUSFARM_SQLITE_BRIDGE_URL') || 'http://127.0.0.1:18766').toString().replace(/\\/$/, '');\nconst u = (msg.req && msg.req.url) ? msg.req.url : '';\nconst q = u.indexOf('?') >= 0 ? u.slice(u.indexOf('?')) : '';\nmsg.method = 'GET';\nmsg.url = base + '/api/channel/status' + q;\nreturn msg;",
        "outputs": 1,
        "noerr": 0,
        "initialize": "",
        "finalize": "",
        "libs": [],
        "x": 440,
        "y": 720,
        "wires": [["cf_hreq_ch_st"]],
    },
    {
        "id": "cf_hreq_ch_st",
        "type": "http request",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "bridge ch status",
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
        "x": 700,
        "y": 720,
        "wires": [["cf_hres_ch_st"]],
    },
    {
        "id": "cf_hres_ch_st",
        "type": "http response",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "채널상태 응답",
        "statusCode": "",
        "headers": {},
        "x": 930,
        "y": 720,
        "wires": [],
    },
    {
        "id": "cf_hin_ch_act",
        "type": "http in",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "채널 액션 POST",
        "url": "/farm/cronusfarm-sqlite/api/channel-action",
        "method": "post",
        "upload": False,
        "swaggerDoc": "",
        "x": 190,
        "y": 780,
        "wires": [["cf_fn_ch_act"]],
    },
    {
        "id": "cf_fn_ch_act",
        "type": "function",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "MQTT+log 수동제어",
        "func": CFN_CH_ACT,
        "outputs": 3,
        "noerr": 0,
        "initialize": "",
        "finalize": "",
        "libs": [],
        "x": 460,
        "y": 780,
        "wires": [["mqtt_out_cf_cmd"], ["sq_http_cf_man"], ["cf_hres_ch_act"]],
    },
    {
        "id": "mqtt_out_cf_cmd",
        "type": "mqtt out",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "cf cmd publish",
        "topic": "",
        "qos": "",
        "retain": "",
        "respTopic": "",
        "contentType": "",
        "userProps": "",
        "correl": "",
        "expiry": "",
        "broker": "d6b7f6c1b2b3c4d5",
        "x": 720,
        "y": 760,
        "wires": [],
    },
    {
        "id": "sq_http_cf_man",
        "type": "http request",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "SQLite manual_event",
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
        "x": 720,
        "y": 800,
        "wires": [[]],
    },
    {
        "id": "cf_hres_ch_act",
        "type": "http response",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "채널액션 응답",
        "statusCode": "",
        "headers": {},
        "x": 720,
        "y": 840,
        "wires": [],
    },
]


def main() -> None:
    nodes = json.loads(MQTT.read_text(encoding="utf-8-sig"))
    ids = {n.get("id") for n in nodes}
    if "cf_fn_ch_act" in ids:
        for n in nodes:
            if n.get("id") == "cf_fn_ch_act":
                n["func"] = CFN_CH_ACT
                break
        MQTT.write_text(json.dumps(nodes, ensure_ascii=False, indent=2), encoding="utf-8")
        print("updated cf_fn_ch_act timer merge")
        return
    idx = next(i for i, n in enumerate(nodes) if n.get("id") == "cf_hres_kv")
    for n in reversed(NEW_NODES):
        nodes.insert(idx + 1, n)
    MQTT.write_text(json.dumps(nodes, ensure_ascii=False, indent=2), encoding="utf-8")
    print("patched", MQTT, "+", len(NEW_NODES), "nodes")


if __name__ == "__main__":
    main()
