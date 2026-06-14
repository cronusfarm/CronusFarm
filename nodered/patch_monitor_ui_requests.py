"""
모니터 UI 요청 일괄 패치 (dashboard + mqtt + bridge).

- B Bed 타일 순서·LED B2 한 줄 표기
- Bed 타임라인 색: LED 노랑 / Pump 파랑 / Fan 녹색
- 타임라인 끝 시각 = DB 최신 state (tele_channel_fact)
- PHW 24h Water Quality 차트 (DB sensor_reading)
- 게이지 범위·salt 스케일(‰) 보정
- 그룹 제목줄 세로 여백 50% 축소
- sf_3team→cronus, HIVEMQ·중복 Mosquitto 제거 (mqtt)

사용: python scripts/patch_monitor_ui_requests.py
      python scripts/merge_nodered_deploy.py --use-split
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
MQTT = ROOT / "nodered" / "flows_cronusfarm_mqtt.json"
BRIDGE = ROOT / "scripts" / "cronusfarm_sqlite_bridge.py"
TIMELINE_PATCH = ROOT / "scripts" / "patch_dashboard_monitor_ai_timeline_bedbox.py"

MOSQUITTO = "d6b7f6c1b2b3c4d5"
DROP_BROKERS = frozenset({"d7013a5209d5fe9b", "mqtt_broker_pi"})
FN_MAP = "201f991e49bff34f"
CHART_UI_OLD = "d7b0b47e7833847a"
CHART_TPL = "ui_tpl_phw_water_24h"

# LED 노랑 / Pump 파랑 / Fan 녹색
COL_LED = ["#FFD54F", "#FFC107"]
COL_PUMP = ["#42A5F5", "#1E88E5", "#29B6F6", "#1565C0"]
COL_FAN = ["#66BB6A", "#43A047", "#2E7D32", "#1B5E20"]


def _fmt_like_a(a_fmt: str, name: str, pin: str) -> str:
    """A Bed 타일 HTML을 복제해 이름·핀만 교체."""
    fmt = re.sub(
        r'(<div class="cf-tile-name">)[^<]+',
        rf"\g<1>{name} ",
        a_fmt,
        count=1,
    )
    return re.sub(r"\(R4-[^)]+\)", f"({pin})", fmt, count=1)


MONITOR_GROUP_CLASS = "cf-monitor-grp"
MONITOR_GROUP_HEADER_CSS = """
/* 모니터 탭 그룹 제목줄(A/B/C Bed, 온실 Data 등) 세로 여백 축소 */
.nr-dashboard-theme .nr-dashboard-group.cf-monitor-grp > md-card > md-toolbar,
.nr-dashboard-theme .nr-dashboard-group.cf-monitor-grp .md-toolbar-tools,
body.nr-dashboard-theme md-card.cf-monitor-grp > md-toolbar .md-toolbar-tools {
  min-height: 22px !important;
  max-height: 28px !important;
  height: auto !important;
  padding-top: 2px !important;
  padding-bottom: 2px !important;
  line-height: 1.1 !important;
}
.nr-dashboard-theme .nr-dashboard-group.cf-monitor-grp .nr-dashboard-cardtitle,
.nr-dashboard-theme md-card.cf-monitor-grp .md-toolbar-tools .md-toolbar-tools-title {
  font-size: 13px !important;
  line-height: 1.1 !important;
  padding-top: 0 !important;
  padding-bottom: 0 !important;
}
"""

PHW_CHART_FMT = r"""<div class="cf-phw-24h">
<style>
.cfw24{font-family:system-ui,sans-serif;color:#e6edf7;padding:2px 0}
.cfw24-hd{font-size:12px;font-weight:800;color:#9db0cc;margin:0 0 2px}
.cfw24-wrap{position:relative;width:100%;min-height:200px;height:200px}
.cfw24-wrap canvas{width:100%!important;height:200px!important;display:block}
.cfw24-msg{font-size:11px;color:#9db0cc;padding:4px 0}
</style>
<div class="cfw24-hd">Water Quality (24h) <span style="font-size:10px;font-weight:400;color:#9db0cc">지금−24h ~ 지금</span></div>
<div id="cf-phw-chart-msg" class="cfw24-msg"></div>
<div class="cfw24-wrap"><canvas id="cf-phw-chart-24h" height="200"></canvas></div>
<script src="/cronusfarm-static/vendor/chart.umd.min.js"></script>
<script type="text/javascript">
(function(scope){
  const API=(location.origin||'')+'/farm/cronusfarm-sqlite/api/sensor/series';
  let chart=null;
  function setMsg(t){var m=document.getElementById('cf-phw-chart-msg');if(m)m.textContent=t||'';}
  function ensureChart(cb){
    if(typeof Chart!=='undefined'){cb();return;}
    var s=document.querySelector('script[src*="chart.umd"]');
    if(s){setTimeout(function(){ensureChart(cb);},150);return;}
    s=document.createElement('script');
    s.src='/cronusfarm-static/vendor/chart.umd.min.js';
    s.onload=cb;
    document.head.appendChild(s);
  }
  async function load(){
    const el=document.getElementById('cf-phw-chart-24h');
    if(!el){setMsg('canvas 없음');return;}
    try{
      const u=API+'?device_id=cronusfarm-01&zone=phw3988&hours=24';
      const r=await fetch(u,{credentials:'same-origin'});
      if(!r.ok){setMsg('API '+r.status);return;}
      const j=await r.json();
      const pts=j.points||[];
      const ph=pts.map(p=>({x:Number(p.ts_ms),y:p.ph})).filter(p=>p.y!=null&&isFinite(p.y));
      const ec=pts.map(p=>({x:Number(p.ts_ms),y:p.ec})).filter(p=>p.y!=null&&isFinite(p.y));
      const tp=pts.map(p=>({x:Number(p.ts_ms),y:p.temp_c})).filter(p=>p.y!=null&&isFinite(p.y));
      if(!ph.length&&!ec.length&&!tp.length){setMsg('24h 데이터 없음');return;}
      function lastY(arr){return arr.length?arr[arr.length-1].y:null;}
      function fnum(v,d){return(v==null||!isFinite(v))?'—':Number(v).toFixed(d);}
      const lp=lastY(ph),le=lastY(ec),lt=lastY(tp);
      const t1=pts.length?new Date(pts[pts.length-1].ts_ms).toLocaleString('ko-KR',{hour:'2-digit',minute:'2-digit'}):'';
      setMsg('최신 pH '+fnum(lp,2)+' · EC '+fnum(le,0)+' µS/cm · Temp '+fnum(lt,1)+'℃  (24h '+pts.length+'건'+(t1?' · '+t1:'')+')');
      const tEnd=Date.now();
      const tStart=tEnd-24*3600*1000;
      function clip(arr){return arr.filter(function(p){return p.x>=tStart&&p.x<=tEnd;});}
      const phC=clip(ph), ecC=clip(ec), tpC=clip(tp);
      const data={datasets:[
        {label:'pH',data:phC,borderColor:'#4fc3f7',borderWidth:2,fill:false,yAxisID:'y',tension:.2,pointRadius:0},
        {label:'EC µS/cm',data:ecC,borderColor:'#ffb74d',borderWidth:2,fill:false,yAxisID:'y1',tension:.2,pointRadius:0},
        {label:'Temp ℃',data:tpC,borderColor:'#81c784',borderWidth:2,fill:false,yAxisID:'y2',tension:.2,pointRadius:0,hidden:tpC.length===0}
      ]};
      const opt={responsive:true,maintainAspectRatio:false,animation:false,
        interaction:{mode:'index',intersect:false},
        plugins:{legend:{display:true,labels:{color:'#cfe0f5',boxWidth:10,font:{size:10}}}},
        scales:{
          x:{type:'linear',min:tStart,max:tEnd,ticks:{color:'#9fb0c4',maxTicksLimit:8,callback:function(v){
            if(v==null||!isFinite(v))return '';
            var d=new Date(v);var h=d.getHours(),m=d.getMinutes();
            return (h<10?'0':'')+h+':'+(m<10?'0':'')+m;
          }}},
          y:{position:'left',title:{display:true,text:'pH',color:'#4fc3f7'},min:0,max:14,ticks:{color:'#4fc3f7'}},
          y1:{position:'right',title:{display:true,text:'EC µS/cm',color:'#ffb74d'},grid:{drawOnChartArea:false},ticks:{color:'#ffb74d'}},
          y2:{position:'right',offset:true,title:{display:true,text:'Temp ℃',color:'#81c784'},min:-20,max:55,grid:{drawOnChartArea:false},ticks:{color:'#81c784'}}
        }};
      ensureChart(function(){
        if(!chart){chart=new Chart(el.getContext('2d'),{type:'line',data,options:opt});}
        else{chart.data=data;chart.options=opt;chart.update();}
      });
    }catch(e){setMsg('오류: '+e);console.warn(e);}
  }
  setInterval(load,60000);
  setTimeout(load,600);
  if(scope&&scope.$watch)scope.$watch('msg',function(){load();});
})(scope);
</script>"""


MQTT_TAB = "b1c5a1f1d7a2a3a1"
SENSOR_PROXY_SPECS = (
    (
        "series",
        "cf_hin_sensor_series",
        "cf_fn_sensor_series",
        "cf_hreq_sensor_series",
        "cf_hres_sensor_series",
        "/farm/cronusfarm-sqlite/api/sensor/series",
        "/api/sensor/series",
        740,
    ),
    (
        "latest",
        "cf_hin_sensor_latest",
        "cf_fn_sensor_latest",
        "cf_hreq_sensor_latest",
        "cf_hres_sensor_latest",
        "/farm/cronusfarm-sqlite/api/sensor/latest",
        "/api/sensor/latest",
        800,
    ),
)


def _sensor_proxy_nodes(
    hin: str,
    fn: str,
    hreq: str,
    hres: str,
    url: str,
    bridge_path: str,
    y: int,
) -> list[dict]:
    fn_code = (
        "const base = (env.get('CRONUSFARM_SQLITE_BRIDGE_URL') || 'http://127.0.0.1:18766').toString().replace(/\\/$/, '');\n"
        "const u = (msg.req && msg.req.url) ? msg.req.url : '';\n"
        "const q = u.indexOf('?') >= 0 ? u.slice(u.indexOf('?')) : '';\n"
        "msg.method = 'GET';\n"
        f"msg.url = base + '{bridge_path}' + q;\n"
        "return msg;"
    )
    return [
        {
            "id": hin,
            "type": "http in",
            "z": MQTT_TAB,
            "name": f"PHW sensor {bridge_path.split('/')[-1]} GET",
            "url": url,
            "method": "get",
            "upload": False,
            "swaggerDoc": "",
            "x": 190,
            "y": y,
            "wires": [[fn]],
        },
        {
            "id": fn,
            "type": "function",
            "z": MQTT_TAB,
            "name": f"→ bridge {bridge_path}",
            "func": fn_code,
            "outputs": 1,
            "timeout": 0,
            "noerr": 0,
            "initialize": "",
            "finalize": "",
            "libs": [],
            "x": 430,
            "y": y,
            "wires": [[hreq]],
        },
        {
            "id": hreq,
            "type": "http request",
            "z": MQTT_TAB,
            "name": "bridge request",
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
            "y": y,
            "wires": [[hres]],
        },
        {
            "id": hres,
            "type": "http response",
            "z": MQTT_TAB,
            "name": "",
            "statusCode": "",
            "headers": {},
            "x": 930,
            "y": y,
            "wires": [],
        },
    ]


def patch_mqtt_sensor_proxy(data: list) -> None:
    by = {n["id"]: n for n in data if isinstance(n, dict) and n.get("id")}
    for _tag, hin, fn, hreq, hres, url, bridge_path, y in SENSOR_PROXY_SPECS:
        if hin in by:
            continue
        for node in _sensor_proxy_nodes(hin, fn, hreq, hres, url, bridge_path, y):
            data.append(node)
            by[node["id"]] = node


def patch_mqtt(data: list) -> None:
    patch_mqtt_sensor_proxy(data)
    out: list = []
    for n in data:
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        if nid in DROP_BROKERS:
            continue
        if n.get("type") == "mqtt-broker" and "hivemq" in str(n.get("broker", "")).lower():
            continue
        node = dict(n)
        if node.get("broker") in DROP_BROKERS:
            node["broker"] = MOSQUITTO
        s = json.dumps(node, ensure_ascii=False)
        if "sf_3team" in s.lower():
            node = json.loads(s.replace("sf_3team", "cronus").replace("SF_3TEAM", "CRONUS"))
        out.append(node)
    data.clear()
    data.extend(out)


def patch_fn_map_salt(node: dict) -> None:
    f = node.get("func") or ""
    f = f.replace("salt: { dp: '113', scale: 1 }", "salt: { dp: '113', scale: 100 }")
    f = f.replace("salt: { dp: '113', scale: 1 },", "salt: { dp: '113', scale: 100 },")
    node["func"] = f


def patch_gauges(by: dict[str, dict]) -> None:
    """게이지 name·title·label·min/max — UI에 보이는 제목은 title/label."""
    specs = {
        "480e017a1bfbfe7b": ("pH", "pH", "pH", 0, 14),
        "2141fe178c3e2c88": ("EC (µS/cm)", "EC (µS/cm)", "µS/cm", 0, 5000),
        "a0a33715ba8ca5eb": ("TDS (ppm)", "TDS (ppm)", "ppm", 0, 5000),
        "f61aebaa74026feb": ("SALT (‰)", "SALT (‰)", "‰", 0, 50),
        "9d76b919dae993f9": ("S.G", "S.G", "SG", 0, 1.05),
        "1800ba1474d7135c": ("Temp (℃)", "Temp (℃)", "℃", -20, 50),
    }
    for gid, (name, title, label, mn, mx) in specs.items():
        n = by.get(gid)
        if not isinstance(n, dict):
            continue
        n["name"] = name
        n["title"] = title
        n["label"] = label
        n["min"] = mn
        n["max"] = mx
        n["group"] = "ui_grp_gh_data"


def _ensure_led_b2(by: dict[str, dict]) -> None:
    """toggle 제거 후 state 노드가 없으면 b1 복제로 생성."""
    if "ui_tpl_state_led_b2" in by:
        return
    src = by.get("ui_tpl_state_led_b1")
    if not isinstance(src, dict):
        return
    n = json.loads(json.dumps(src))
    n["id"] = "ui_tpl_state_led_b2"
    n["name"] = "LED B2 상태"
    n["order"] = 2
    n["wires"] = [[]]
    by["ui_tpl_state_led_b2"] = n


def patch_monitor_group_classes(by: dict[str, dict]) -> None:
    """모니터 탭 ui_group에 cf-monitor-grp 클래스 부여(제목줄 CSS용)."""
    for n in by.values():
        if n.get("type") != "ui_group" or n.get("tab") != "ui_tab_monitor":
            continue
        c = (n.get("className") or "").strip()
        if MONITOR_GROUP_CLASS not in c.split():
            n["className"] = f"{c} {MONITOR_GROUP_CLASS}".strip()


def _rewire_toggle_to_state(by: dict[str, dict]) -> None:
    old, new = "ui_tpl_toggle_led_b2", "ui_tpl_state_led_b2"
    for n in by.values():
        if not isinstance(n, dict):
            continue
        wires = n.get("wires")
        if not isinstance(wires, list):
            continue
        for i, outs in enumerate(wires):
            if not isinstance(outs, list):
                continue
            wires[i] = [new if x == old else x for x in outs]


def patch_bed_b(by: dict[str, dict]) -> None:
    """B Bed 타일: A Bed와 동일 HTML·height=1(한 줄)."""
    by.pop("ui_tpl_toggle_led_b2", None)
    _ensure_led_b2(by)
    _rewire_toggle_to_state(by)
    clone_specs = [
        ("ui_tpl_state_led_b1", "ui_tpl_state_led_a1", 1, "LED B1", "R4-D6"),
        ("ui_tpl_state_led_b2", "ui_tpl_state_led_a1", 2, "LED B2", "R4-D13"),
        ("ui_tpl_state_pump_b1", "ui_tpl_state_pump_a1", 3, "Pump B1", "R4-D7"),
        ("ui_tpl_state_pump_b2", "ui_tpl_state_pump_a1", 4, "Pump B2", "R4-D8"),
        ("ui_tpl_state_fan_b1", "ui_tpl_state_fan_a1", 5, "Fan B1", "R4-D11"),
        ("ui_tpl_state_fan_b2", "ui_tpl_state_fan_a1", 6, "Fan B2", "R4-D12"),
    ]
    for nid, src_id, order, name, pin in clone_specs:
        n = by.get(nid)
        src = by.get(src_id)
        if not isinstance(n, dict) or not isinstance(src, dict):
            continue
        n["order"] = order
        n["format"] = _fmt_like_a(src.get("format") or "", name, pin)
        n["group"] = "ui_grp_b"
        n["width"] = 6
        n["height"] = 1
        n["wires"] = [[]]


def patch_timeline_colors_in_patch_script() -> None:
    if not TIMELINE_PATCH.is_file():
        return
    txt = TIMELINE_PATCH.read_text(encoding="utf-8")
    txt = re.sub(
        r'col_a = \[.*?\]',
        "col_a = " + json.dumps(COL_LED + COL_PUMP[:2] + COL_FAN[:2]),
        txt,
        count=1,
    )
    txt = re.sub(
        r'col_b = \[.*?\]',
        "col_b = " + json.dumps(COL_LED + COL_PUMP[:2] + COL_FAN[:2]),
        txt,
        count=1,
    )
    txt = re.sub(
        r'col_c = \[.*?\]',
        "col_c = " + json.dumps(COL_PUMP[:2]),
        txt,
        count=1,
    )
    txt = re.sub(
        r'col_d = \[.*?\]',
        "col_d = " + json.dumps(COL_PUMP[:2]),
        txt,
        count=1,
    )
    TIMELINE_PATCH.write_text(txt, encoding="utf-8")


def patch_bridge_timeline_latest() -> None:
    txt = BRIDGE.read_text(encoding="utf-8")
    if "latest_row = cur.fetchone()" in txt and "timeline_latest_fix" in txt:
        return
    old = """                    if points:
                        last = points[-1]
                        last_ts = int(last["ts_ms"])
                        if last_ts < now_ms:
                            points.append(
                                {
                                    "ts_ms": now_ms,
                                    "state": last["state"],
                                    "auto_mode": last.get("auto_mode"),
                                }
                            )
                body = {
                    "device_id": device_id,
                    "channel_key": channel,
                    "hours": hours,
                    "anchor_ts_ms": anchor_ts_ms,
                    "window_end_ms": now_ms,
                    "points": points,
                }"""
    new = """                    # timeline_latest_fix: 창 끝 = DB 최신 state (tele 적재·수동/스케줄 반영)
                    cur.execute(
                        \"\"\"SELECT ts_ms, state, auto_mode FROM tele_channel_fact
                        WHERE device_id=? AND channel_key=? ORDER BY ts_ms DESC LIMIT 1\"\"\",
                        (device_id, channel),
                    )
                    latest_row = cur.fetchone()
                    if latest_row is not None:
                        st_now = latest_row[1]
                        au_now = latest_row[2]
                        if points and int(points[-1]["ts_ms"]) >= now_ms - 5000:
                            points[-1] = {
                                "ts_ms": now_ms,
                                "state": st_now,
                                "auto_mode": au_now,
                            }
                        else:
                            points.append(
                                {
                                    "ts_ms": now_ms,
                                    "state": st_now,
                                    "auto_mode": au_now,
                                }
                            )
                    elif points:
                        last = points[-1]
                        last_ts = int(last["ts_ms"])
                        if last_ts < now_ms:
                            points.append(
                                {
                                    "ts_ms": now_ms,
                                    "state": last["state"],
                                    "auto_mode": last.get("auto_mode"),
                                }
                            )
                body = {
                    "device_id": device_id,
                    "channel_key": channel,
                    "hours": hours,
                    "anchor_ts_ms": anchor_ts_ms,
                    "window_end_ms": now_ms,
                    "points": points,
                }"""
    if old not in txt:
        return
    txt = txt.replace(old, new, 1)
    if "/api/sensor/series" not in txt:
        sensor_get = '''
            if path == "/api/sensor/series":
                qs = parse_qs(parsed.query or "")
                device_id = (qs.get("device_id") or ["cronusfarm-01"])[0].strip() or "cronusfarm-01"
                zone = (qs.get("zone") or ["phw3988"])[0].strip() or "phw3988"
                hours = int((qs.get("hours") or ["24"])[0] or 24)
                if hours < 1 or hours > 168:
                    hours = 24
                cutoff = int(time.time() * 1000) - hours * 3600 * 1000
                with lock:
                    cur = conn.cursor()
                    cur.execute(
                        """SELECT ts_ms, ph, ec, temp_c FROM sensor_reading
                        WHERE device_id=? AND zone=? AND ts_ms >= ? ORDER BY ts_ms ASC LIMIT 5000""",
                        (device_id, zone, cutoff),
                    )
                    pts = [
                        {
                            "ts_ms": int(r[0]),
                            "ph": r[1],
                            "ec": r[2],
                            "temp_c": r[3],
                        }
                        for r in cur.fetchall()
                    ]
                body = {
                    "ok": True,
                    "device_id": device_id,
                    "zone": zone,
                    "hours": hours,
                    "points": pts,
                }
                raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self._cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
'''
        txt = txt.replace(
            '            if path == "/api/sensor/latest":',
            sensor_get + '\n            if path == "/api/sensor/latest":',
            1,
        )
    BRIDGE.write_text(txt, encoding="utf-8")


def main() -> int:
    patch_timeline_colors_in_patch_script()
    subprocess.run([sys.executable, str(TIMELINE_PATCH)], cwd=str(ROOT), check=False)
    patch_bridge_timeline_latest()

    dash = json.loads(DASH.read_text(encoding="utf-8-sig"))
    by: dict[str, dict] = {}
    for n in dash:
        if isinstance(n, dict) and n.get("id"):
            by[n["id"]] = n

    GH_GROUP = "ui_grp_gh_data"
    if GH_GROUP not in by:
        by[GH_GROUP] = {
            "id": GH_GROUP,
            "type": "ui_group",
            "name": "양액 상태 Data",
            "tab": "ui_tab_monitor",
            "order": 6,
            "disp": True,
            "width": "12",
            "collapse": False,
            "className": "cf-gh-data-dark",
        }
    else:
        by[GH_GROUP]["tab"] = "ui_tab_monitor"
        by[GH_GROUP]["name"] = "온실 Data (PHW3988)"
        by[GH_GROUP]["className"] = "cf-gh-data-dark"

    patch_bed_b(by)
    patch_monitor_group_classes(by)
    patch_gauges(by)
    if FN_MAP in by:
        patch_fn_map_salt(by[FN_MAP])

    by.pop(CHART_UI_OLD, None)
    by[CHART_TPL] = {
        "id": CHART_TPL,
        "type": "ui_template",
        "z": "tab_cronus_dash",
        "group": "ui_grp_gh_data",
        "name": "Water Quality (24h)",
        "order": 4,
        "width": "12",
        "height": 8,
        "format": PHW_CHART_FMT,
        "storeOutMessages": True,
        "fwdInMessages": True,
        "resendOnRefresh": True,
        "templateScope": "local",
        "className": "",
        "x": 400,
        "y": 900,
        "wires": [[]],
    }

    for n in by.values():
        s = json.dumps(n, ensure_ascii=False)
        if "sf_3team" in s.lower():
            n.update(json.loads(s.replace("sf_3team", "cronus")))

    if "ui_tpl_css_cronus" in by:
        fmt = by["ui_tpl_css_cronus"].get("format") or ""
        fmt = re.sub(
            r"/\* 온실 Data 그룹 제목줄[\s\S]*?line-height: 1\.2 !important;\s*\}\s*",
            "",
            fmt,
            count=1,
        )
        if MONITOR_GROUP_HEADER_CSS.strip() not in fmt:
            if "</style>" in fmt:
                fmt = fmt.replace("</style>", MONITOR_GROUP_HEADER_CSS + "\n</style>", 1)
            else:
                fmt += "\n<style>" + MONITOR_GROUP_HEADER_CSS + "</style>\n"
            by["ui_tpl_css_cronus"]["format"] = fmt

    DASH.write_text(json.dumps(list(by.values()), ensure_ascii=False), encoding="utf-8")

    mqtt = json.loads(MQTT.read_text(encoding="utf-8-sig"))
    patch_mqtt(mqtt)
    MQTT.write_text(json.dumps(mqtt, ensure_ascii=False), encoding="utf-8")

    print("OK patch_monitor_ui_requests (dashboard, mqtt, bridge, timeline colors)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
