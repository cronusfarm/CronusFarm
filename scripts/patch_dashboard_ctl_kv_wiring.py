"""관제 허브 KV: 슬라이더마다 topic 고정(change) + 함수 보강 + 테스트 inject."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
p = root / "nodered" / "flows_cronusfarm_dashboard.json"
data = json.loads(p.read_text(encoding="utf-8-sig"))

by_id = {n["id"]: n for n in data if isinstance(n, dict) and "id" in n}

changes = [
    ("cf_chg_kv_ph", "ctl_target_ph", "cf_sl_ph"),
    ("cf_chg_kv_ec", "ctl_target_ec", "cf_sl_ec"),
    ("cf_chg_kv_temp", "ctl_target_temp_c", "cf_sl_temp"),
    ("cf_chg_kv_rh", "ctl_target_rh_pct", "cf_sl_rh"),
]

new_nodes = []
for nid, topic, _slider_id in changes:
    if nid in by_id:
        continue
    new_nodes.append(
        {
            "id": nid,
            "type": "change",
            "z": "tab_cronus_dash",
            "name": f"KV topic={topic}",
            "rules": [
                {
                    "t": "set",
                    "p": "topic",
                    "pt": "str",
                    "to": topic,
                    "tot": "str",
                }
            ],
            "action": "",
            "property": "",
            "from": "",
            "to": "",
            "reg": False,
            "x": 560,
            "y": 120,
            "wires": [["cf_fn_ctl_kv"]],
        }
    )

for n in new_nodes:
    data.append(n)
    by_id[n["id"]] = n

by_id = {n["id"]: n for n in data if isinstance(n, dict) and "id" in n}

for nid, topic, slider_id in changes:
    if slider_id in by_id:
        by_id[slider_id]["wires"] = [[nid]]
        by_id[slider_id]["passthru"] = True
        by_id[slider_id]["topicType"] = "str"

fn_src = r"""const dis = (env.get('CRONUSFARM_SQLITE_DISABLE') || '').toString().trim();
if (dis === '1' || dis.toLowerCase() === 'true') return null;
const devId = flow.get('deviceId') || 'cronusfarm-01';
const base = (env.get('CRONUSFARM_SQLITE_BRIDGE_URL') || 'http://127.0.0.1:18766').toString().replace(/\/$/, '');
let key = (msg.topic || '').toString().trim();
if (!key && msg.properties && msg.properties.topic) key = String(msg.properties.topic).trim();
if (!key) {
  node.warn('KV: topic 없음 — Change 노드·슬라이더 설정 확인');
  return null;
}
msg.method = 'POST';
msg.url = base + '/settings/kv';
msg.headers = { 'Content-Type': 'application/json; charset=utf-8' };
msg.payload = JSON.stringify({
  device_id: devId,
  key,
  value: String(msg.payload)
});
return msg;"""

if "cf_fn_ctl_kv" in by_id:
    by_id["cf_fn_ctl_kv"]["func"] = fn_src

if "cf_http_ctl_kv" in by_id:
    by_id["cf_http_ctl_kv"]["senderr"] = True

if "cf_inj_kv_smoke" not in by_id:
    inj = {
        "id": "cf_inj_kv_smoke",
        "type": "inject",
        "z": "tab_cronus_dash",
        "name": "KV 스모크 테스트",
        "props": [{"p": "payload"}, {"p": "topic", "vt": "str"}],
        "repeat": "",
        "crontab": "",
        "once": False,
        "onceDelay": "0.1",
        "topic": "ctl_target_ph",
        "payload": "6.66",
        "payloadType": "num",
        "x": 280,
        "y": 200,
        "wires": [["cf_chg_kv_ph"]],
    }
    data.append(inj)

p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
print("OK patch KV wiring:", p)
