"""설정 탭에 '관제 허브' 그룹(환경 목표 슬라이더 → SQLite KV) 추가."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
dash_path = root / "nodered" / "flows_cronusfarm_dashboard.json"
data = json.loads(dash_path.read_text(encoding="utf-8-sig"))

GROUP_ID = "ui_grp_ctl_hub"
if any(isinstance(n, dict) and n.get("id") == GROUP_ID for n in data):
    print("skip: already has", GROUP_ID)
    raise SystemExit(0)

insert_at = 0
for i, n in enumerate(data):
    if isinstance(n, dict) and n.get("id") == "ui_grp_farm":
        insert_at = i + 1
        break

group = {
    "id": GROUP_ID,
    "type": "ui_group",
    "name": "관제 허브 — 환경 목표·임계 (SQLite)",
    "tab": "ui_tab_settings",
    "order": 0,
    "disp": True,
    "width": "12",
    "collapse": False,
}

banner = {
    "id": "cf_tpl_ctl_banner",
    "type": "ui_template",
    "z": "tab_cronus_dash",
    "group": GROUP_ID,
    "name": "관제 허브 안내",
    "order": 1,
    "width": "12",
    "height": "2",
    "format": """<div class="cf-ctl-hub">
<style>
.cf-ctl-hub{font-family:'Noto Sans KR',sans-serif;color:#e6edf7;padding:10px 12px;background:linear-gradient(135deg,rgba(46,125,50,.25),rgba(13,71,161,.2));border-radius:14px;border:1px solid rgba(255,255,255,.08)}
.cf-ctl-hub .t{font-size:15px;font-weight:700;margin-bottom:6px;color:#b9f6ca}
.cf-ctl-hub .s{font-size:12px;line-height:1.45;color:#9db0cc;opacity:.95}
.cf-ctl-hub .badges{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.cf-ctl-hub .bd{font-size:11px;padding:4px 10px;border-radius:999px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.08)}
</style>
<div class="t">스마트팜 관제 허브</div>
<div class="s">목표 pH·EC·온도·습도를 설정하면 SQLite <code>settings_kv</code>에 저장됩니다. 시계열 그래프는 Grafana(InfluxDB)에서 확인하세요. 브리지 미기동 시 슬라이더는 HTTP 오류를 무시합니다.</div>
<div class="badges"><span class="bd">Influx: tele + guard_*</span><span class="bd">SQLite: 이력·설정</span><span class="bd">DEVICE_ID: flow.deviceId</span></div>
</div>""",
    "storeOutMessages": False,
    "fwdInMessages": False,
    "resendOnRefresh": True,
    "templateScope": "local",
    "x": 100,
    "y": 100,
    "wires": [[]],
}

sliders = [
    ("cf_sl_ph", "목표 pH", "ctl_target_ph", 0, 14, 0.1, 6.5, 2),
    ("cf_sl_ec", "목표 EC (mS/cm)", "ctl_target_ec", 0, 3, 0.05, 1.2, 3),
    ("cf_sl_temp", "목표 온도 (°C)", "ctl_target_temp_c", 10, 35, 0.5, 24, 4),
    ("cf_sl_rh", "목표 습도 (%)", "ctl_target_rh_pct", 30, 90, 1, 65, 5),
]

slider_nodes = []
for sid, label, topic, mn, mx, st, ini, ordv in sliders:
    slider_nodes.append(
        {
            "id": sid,
            "type": "ui_slider",
            "z": "tab_cronus_dash",
            "name": label,
            "label": label,
            "tooltip": "변경 시 SQLite에 저장",
            "group": GROUP_ID,
            "order": ordv,
            "width": "6",
            "height": "1",
            "passthru": False,
            "outs": "all",
            "topic": topic,
            "min": mn,
            "max": mx,
            "step": st,
            "x": 200,
            "y": 100,
            "wires": [["cf_fn_ctl_kv"]],
        }
    )

fn_kv = {
    "id": "cf_fn_ctl_kv",
    "type": "function",
    "z": "tab_cronus_dash",
    "name": "관제 목표→SQLite KV",
    "func": r"""const dis = (env.get('CRONUSFARM_SQLITE_DISABLE') || '').toString().trim();
if (dis === '1') return null;
const devId = flow.get('deviceId') || 'cronusfarm-01';
const base = (env.get('CRONUSFARM_SQLITE_BRIDGE_URL') || 'http://127.0.0.1:18766').toString().replace(/\/$/, '');
msg.method = 'POST';
msg.url = base + '/settings/kv';
msg.headers = { 'Content-Type': 'application/json; charset=utf-8' };
msg.payload = JSON.stringify({
  device_id: devId,
  key: (msg.topic || 'kv').toString(),
  value: String(msg.payload)
});
return msg;""",
    "outputs": 1,
    "noerr": 0,
    "initialize": "",
    "finalize": "",
    "libs": [],
    "x": 700,
    "y": 120,
    "wires": [["cf_http_ctl_kv"]],
}

http_kv = {
    "id": "cf_http_ctl_kv",
    "type": "http request",
    "z": "tab_cronus_dash",
    "name": "SQLite KV POST",
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
    "x": 920,
    "y": 120,
    "wires": [[]],
}

new_nodes = [group, banner, *slider_nodes, fn_kv, http_kv]
for n in new_nodes:
    data.insert(insert_at, n)
    insert_at += 1

dash_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
print("OK append ctl hub nodes:", len(new_nodes))
