# -*- coding: utf-8 -*-
"""
모니터 확장 패치: R3/R4·USB 링크, Farm KMA 잘림, 양액 게이지명, LED 누적광량 차트.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from _r4_status_oneline import formats as _r4_status_formats  # noqa: E402

_r4_fmts = _r4_status_formats()

DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

FN_CALC = "fn_calc_online"
FN_SEEN_TELE = "fn_seen_tele"
TPL_SUMMARY = "ui_tpl_farm_route_summary"
TPL_CONN = "ui_tpl_conn_line"
TPL_MQTT = "ui_tpl_status_line"
TPL_R3 = "ui_tpl_r3_panel_line"
TPL_USB = "ui_tpl_r4_usb_line"
TPL_FARM = "ui_tpl_farm_env"
TPL_DLI = "ui_tpl_led_dli_24h"
GH_GROUP = "ui_grp_gh_data"
CHART_PHW = "ui_tpl_phw_water_24h"

FN_CALC_CODE = r"""const now=Date.now();
const ls=flow.get('arduinoLastStatusMs')||0;
const lt=flow.get('arduinoLastTeleMs')||0;
const TELE_MS=90000;
const teleOk = lt > 0 && (now - lt) < TELE_MS;
const usbMs = flow.get('arduinoLastUsbMs') || 0;
const mqttMs = flow.get('arduinoLastMqttTeleMs') || 0;
const USB_MS = 90000;
const usbSerialOk = usbMs > 0 && (now - usbMs) < USB_MS;
const mqttTeleOk = mqttMs > 0 && (now - mqttMs) < TELE_MS;
const farmLink = (flow.get('lastFarmLink') || '').toString();
const usbPrimary = ((env.get('CRONUSFARM_USB_PRIMARY') || '1').toString().trim() === '1');
function normStatus(v) {
  let s = (v === undefined || v === null) ? '' : String(v);
  s = s.replace(/^\uFEFF/, '').trim().replace(/^['\"]+|['\"]+$/g, '');
  let rl0 = s.toLowerCase();
  if (rl0.charAt(0) === '{') {
    try {
      const o = JSON.parse(s);
      if (o && typeof o.state === 'string') { s = String(o.state).trim(); }
    } catch (e) { /* 무시 */ }
  }
  return s;
}
const retain = normStatus(flow.get('lastStatusStr'));
const rl = retain.toLowerCase();
const retainOn = rl === 'online';
const retainOff = rl === 'offline';
function teleRawFromFlow() {
  const cached = (flow.get('lastTeleStr') || '').toString();
  const pl = msg.payload;
  if (typeof pl === 'string' && pl.length && pl.indexOf('S:') >= 0) {
    return pl;
  }
  return cached;
}
const raw = teleRawFromFlow();
function wifiFromTele(s) {
  const m = String(s||'').match(/\|\s*W:([^|]+)/);
  if (!m) {
    const c = (flow.get('lastWifiIp')||'').toString();
    return { ok: !!c && c !== '0.0.0.0', hint: 'W: 없음' };
  }
  const w = m[1].trim();
  const ipM = w.match(/ip=(\d+\.\d+\.\d+\.\d+)/);
  const ip = ipM ? ipM[1] : '';
  const ok = !!(ip && ip !== '0.0.0.0');
  if (ok) flow.set('lastWifiIp', ip);
  return { ok, hint: w.length > 44 ? w.slice(0, 44) + '…' : w };
}
function farmLinkFromTele(s) {
  const m = String(s||'').match(/\|\s*L:(usb|mqtt)/);
  if (m) return m[1];
  return '';
}
function panelR3FromTele(s) {
  const m = String(s||'').match(/\|\s*P:([^|]+)/);
  if (!m) return { ok: null, hint: 'tele P: 없음' };
  const p = m[1].trim();
  const ready = /ready=1/.test(p);
  const rcM = p.match(/i2c_rc=(\d+)/);
  const rc = rcM ? parseInt(rcM[1], 10) : 255;
  const gotM = p.match(/got=(\d+)/);
  const got = gotM ? parseInt(gotM[1], 10) : 0;
  const rxM = p.match(/rxage=(\d+)s/);
  const rx = rxM ? parseInt(rxM[1], 10) : 9999;
  const ok = ready && (rc === 0 || got > 0);
  let hint = p.length > 56 ? p.slice(0, 56) + '…' : p;
  if (!ok) {
    if (rc === 2 && got <= 0) {
      hint = 'I2C 0x38 NACK — R3 미응답(배선·전원·R3펌웨어)';
    } else if (rc === 3) {
      hint = 'I2C 데이터 NACK — R3 통신 오류';
    } else if (!ready && rx >= 60) {
      hint = 'R3 링크 끊김 ' + rx + 's — SDA/SCL·전원 확인';
    } else if (!ready) {
      hint = 'R3 미준비 rc=' + rc + ' got=' + got;
    }
  } else if (got > 0 && rc !== 0) {
    hint = 'R3 OK(이벤트수신) rc=' + rc;
  }
  return { ok, hint };
}
function r3DisplayStable(live) {
  let disp = flow.get('r3DispOk');
  const lastAt = flow.get('r3DispAt') || 0;
  const HOLD_MS = 8000;
  if (live.ok === true) {
    flow.set('r3FailStreak', 0);
    if (disp !== true) {
      const n = (flow.get('r3OkStreak') || 0) + 1;
      flow.set('r3OkStreak', n);
      if (n >= 2 || (now - lastAt) > HOLD_MS) {
        flow.set('r3DispOk', true);
        flow.set('r3DispAt', now);
        disp = true;
      }
    }
  } else if (live.ok === false) {
    flow.set('r3OkStreak', 0);
    if (disp !== false) {
      const n = (flow.get('r3FailStreak') || 0) + 1;
      flow.set('r3FailStreak', n);
      if (n >= 3 || (now - lastAt) > HOLD_MS) {
        flow.set('r3DispOk', false);
        flow.set('r3DispAt', now);
        disp = false;
      }
    }
  }
  const show = flow.get('r3DispOk');
  return {
    ok: show === true ? true : (show === false ? false : null),
    hint: live.hint
  };
}
const wifi = wifiFromTele(raw);
const teleLink = farmLinkFromTele(raw);
if (teleLink === 'usb') flow.set('lastFarmLink', 'usb');
else if (teleLink === 'mqtt') flow.set('lastFarmLink', 'mqtt_wifi');
const r3live = panelR3FromTele(raw);
const r3 = r3DisplayStable(r3live);
const wifiDeviceOk = !!wifi.ok;
const linkTag = teleLink || farmLink;
let usbAge = usbSerialOk ? Math.floor((now - usbMs) / 1000) : null;
if (usbAge === null && teleOk && teleLink === 'usb') {
  usbAge = Math.floor((now - lt) / 1000);
}
const usbFarmOk = usbAge !== null && usbAge < Math.floor(USB_MS / 1000);
const mqttWifiFarmOk = (mqttTeleOk || (teleOk && teleLink === 'mqtt')) && wifiDeviceOk;
const controlOk = !!(usbFarmOk || mqttWifiFarmOk);
let degraded = false;
let routeTitle = 'farm 제어 · 확인 중';
let routeDetail = 'tele 수신 대기';
let controlState = '—';
if (controlOk) {
  controlState = '정상';
  if (usbFarmOk && !mqttWifiFarmOk) {
    degraded = usbPrimary && !wifiDeviceOk;
    routeTitle = usbPrimary ? 'farm 제어 · USB primary 정상' : 'farm 제어 · USB 경로 정상';
    const bits = [];
    if (usbPrimary) bits.push('WiFi MQTT 대기(백업)');
    if (!wifiDeviceOk) bits.push('R4 WiFi 미연결');
    else bits.push('R4 WiFi 연결(백업 준비)');
    routeDetail = bits.join(' · ');
  } else if (mqttWifiFarmOk) {
    routeTitle = usbPrimary ? 'farm 제어 · MQTT fallback 정상' : 'farm 제어 · WiFi MQTT 정상';
    routeDetail = wifiDeviceOk ? ('USB 단절 · WiFi ' + ((flow.get('lastWifiIp')||'').toString() || '연결')) : 'WiFi 상태 확인';
  } else {
    routeTitle = 'farm 제어 · 경로 정상';
    routeDetail = 'tele 수신 중';
  }
} else {
  controlState = '불가';
  routeTitle = 'farm 제어 · 전 경로 단절';
  const bits = [];
  if (!usbFarmOk) bits.push('USB tele 없음');
  if (!mqttWifiFarmOk) bits.push('WiFi MQTT tele 없음');
  if (!wifiDeviceOk) bits.push('R4 WiFi ip=0');
  routeDetail = bits.join(' · ') || '점검 필요';
}
const teleAge = lt ? Math.floor((now - lt) / 1000) : null;
const mqttTeleAge = mqttTeleOk ? Math.floor((now - mqttMs) / 1000) : (teleOk && teleLink === 'mqtt' ? teleAge : null);
const wifiIp = (flow.get('lastWifiIp') || '').toString();
let connOk = controlOk;
if (retainOff && !controlOk) connOk = false;
else if (retain && !controlOk && !retainOn) connOk = false;
msg.payload = {
  online: !!controlOk,
  controlOk: !!controlOk,
  degraded: !!degraded,
  routeTitle: routeTitle,
  routeDetail: routeDetail,
  controlState: controlState,
  usbPrimary: !!usbPrimary,
  wifiDeviceOk: wifiDeviceOk,
  mqttWifiFarmOk: !!mqttWifiFarmOk,
  usbFarmOk: !!usbFarmOk,
  wifiOk: wifiDeviceOk,
  connOk: !!connOk,
  wifiHint: wifiDeviceOk ? (wifi.hint || '연결') : (wifi.hint || 'ip=0.0.0.0'),
  wifiIp: wifiIp && wifiIp !== '0.0.0.0' ? wifiIp : '',
  r3ok: r3.ok,
  r3hint: r3.hint,
  usbOk: !!usbFarmOk,
  usbAge: usbAge,
  mqttTeleAge: mqttTeleAge,
  teleAge: teleAge,
  statusAge: ls ? Math.floor((now - ls) / 1000) : null,
  statusRetain: controlOk ? 'online' : retain,
  preview: raw
};
msg._ok = msg.payload.online;
msg._connOk = msg.payload.connOk;
msg._controlOk = msg.payload.controlOk;
msg._wifiOk = msg.payload.wifiDeviceOk;
msg.connLineOk = msg.payload.controlOk;
msg._wifiHint = msg.payload.wifiHint;
msg._wifiIp = msg.payload.wifiIp;
msg._r3ok = msg.payload.r3ok;
msg._r3hint = msg.payload.r3hint;
msg._usbOk = msg.payload.usbFarmOk;
msg._usbAge = msg.payload.usbAge;
msg.teleAge = teleAge;
msg.statusAge = msg.payload.statusAge;
msg.statusRetain = msg.payload.statusRetain;
msg.telePreview = raw;
return [msg, msg, msg, msg, msg];"""

FN_SEEN_TELE_CODE = r"""let p = msg.payload;
if (Buffer.isBuffer(p)) p = p.toString('utf8');
else if (p != null && typeof p !== 'string') p = String(p);
else p = (p || '').toString();
const now = Date.now();
flow.set('arduinoLastTeleMs', now);
flow.set('lastTeleStr', (p || '').toString());
const via = (msg.via || msg._via || '').toString().toLowerCase();
const lm = (p || '').match(/\|\s*L:(usb|mqtt)/);
if (via.indexOf('usb') >= 0 || via.indexOf('serial') >= 0 || via.indexOf('bridge') >= 0) {
  flow.set('arduinoLastUsbMs', now);
  flow.set('lastFarmLink', 'usb');
} else if (via) {
  flow.set('arduinoLastMqttTeleMs', now);
  flow.set('lastFarmLink', 'mqtt_wifi');
} else if (lm && lm[1] === 'usb') {
  flow.set('arduinoLastUsbMs', now);
  flow.set('lastFarmLink', 'usb');
} else if (lm && lm[1] === 'mqtt') {
  flow.set('arduinoLastMqttTeleMs', now);
  flow.set('lastFarmLink', 'mqtt_wifi');
}
return msg;"""

_FMT_SUMMARY = _r4_fmts["ui_tpl_farm_route_summary"]
_FMT_CONN = _r4_fmts["ui_tpl_conn_line"]
_FMT_MQTT = _r4_fmts["ui_tpl_status_line"]
_FMT_R3 = _r4_fmts["ui_tpl_r3_panel_line"]
_FMT_USB = _r4_fmts["ui_tpl_r4_usb_line"]

DLI_CHART_FMT = r"""<div class="cf-dli-24h">
<style>
.cfdli{font-family:system-ui,sans-serif;color:#e6edf7;padding:2px 0}
.cfdli-hd{font-size:12px;font-weight:800;color:#9db0cc;margin:0 0 2px}
.cfdli-sub{font-size:10px;color:#7a8fa8;margin:0 0 6px;line-height:1.35}
.cfdli-wrap{position:relative;width:100%;min-height:200px;height:200px}
.cfdli-wrap canvas{width:100%!important;height:200px!important;display:block}
.cfdli-msg{font-size:11px;color:#c5d6ea;padding:4px 0}
.cfdli-sum{display:flex;flex-wrap:wrap;gap:10px 16px;margin:0 0 6px;font-size:11px;color:#e8f0ff}
.cfdli-sum span{padding:4px 10px;border-radius:8px;background:rgba(255,255,255,0.10);border:1px solid rgba(255,255,255,0.16);font-weight:600}
.cfdli-sum .a{color:#FFE082;background:rgba(255,213,79,0.14);border-color:rgba(255,213,79,0.35)}
.cfdli-sum .b{color:#81D4FA;background:rgba(79,195,247,0.14);border-color:rgba(79,195,247,0.35)}
.cfdli-sum .inst{color:#f0f6ff;background:rgba(200,220,255,0.12);border-color:rgba(200,220,255,0.28)}
</style>
<div class="cfdli-hd">누적 광량 (48h) · LED A1 / B1 <span class="cf-muted" style="font-size:10px;font-weight:400">지금-48H ~ 지금</span></div>
<div class="cfdli-sub">LED ON 구간 적분 · PPFD {{msg.ppfd || 200}} µmol/m²/s 가정 · 우상향=누적 DLI (mol/m²)</div>
<div id="cf-dli-chart-msg" class="cfdli-msg"></div>
<div id="cf-dli-chart-sum" class="cfdli-sum"></div>
<div class="cfdli-wrap"><canvas id="cf-dli-chart-24h" height="200"></canvas></div>
<script src="/cronusfarm-static/vendor/chart.umd.min.js"></script>
<script type="text/javascript">
(function(scope){
  const PPFD = Number(scope && scope.ppfd) || 200;
  const API=(location.origin||'')+'/farm/cronusfarm-sqlite/api/channel/timeline/batch';
  const API_TIME=(location.origin||'')+'/farm/cronusfarm-sqlite/api/time/status?device_id=cronusfarm-01';
  let chart=null;
  function setMsg(t){var m=document.getElementById('cf-dli-chart-msg');if(m)m.textContent=t||'';}
  function setSum(html){var m=document.getElementById('cf-dli-chart-sum');if(m)m.innerHTML=html||'';}
  async function nowMs(){
    try{
      if(window.__cfPiNowMs && (Date.now() - window.__cfPiNowMsAt) < 15000) return window.__cfPiNowMs;
      const r=await fetch(API_TIME,{credentials:'same-origin'});
      if(r.ok){
        const j=await r.json();
        const ms=Number(j.pi_ts_ms);
        if(ms && isFinite(ms)){
          window.__cfPiNowMs = ms;
          window.__cfPiNowMsAt = Date.now();
          return ms;
        }
      }
    }catch(e){}
    return Date.now();
  }
  function ensureChart(cb){
    if(typeof Chart!=='undefined'){cb();return;}
    var s=document.querySelector('script[src*="chart.umd"]');
    if(s){setTimeout(function(){ensureChart(cb);},150);return;}
    s=document.createElement('script');
    s.src='/cronusfarm-static/vendor/chart.umd.min.js';
    s.onload=cb;
    document.head.appendChild(s);
  }
  function integrateCumulative(points, tStart, tEnd, ppfd){
    const pts=(points||[]).slice().sort(function(a,b){return a.ts_ms-b.ts_ms;});
    if(!pts.length) return {inst:0, total:0, series:[]};
    let cum=0, series=[{x:tStart,y:0}];
    for(let i=0;i<pts.length;i++){
      const segStart=Math.max(tStart, Number(pts[i].ts_ms));
      const st=Number(pts[i].state)===1?1:0;
      const segEnd=Math.min(tEnd, (i+1<pts.length)?Number(pts[i+1].ts_ms):tEnd);
      if(segEnd<=segStart) continue;
      const dt=Math.max(0,segEnd-segStart)/1000;
      if(st===1) cum += ppfd*dt;
      series.push({x:segEnd, y:cum/1e6});
    }
    const last=pts[pts.length-1];
    const inst=(Number(last.state)===1)?ppfd:0;
    return {inst, total:cum/1e6, series:series};
  }
  function cfAxisTicks48h(tStart,tEnd){
    var span=tEnd-tStart;
    var step=span>30*3600*1000?2*3600*1000:3600*1000;
    return{color:'#9fb0c4',maxTicksLimit:30,autoSkip:false,stepSize:step,callback:function(v){
      if(v==null||!isFinite(v))return '';
      var d=new Date(v),mm=d.getMonth()+1,dd=d.getDate(),h=d.getHours(),mi=d.getMinutes();
      var tm=(h<10?'0':'')+h+':'+(mi<10?'0':'')+mi;
      if(span>36*3600*1000)return mm+'/'+dd+' '+tm;
      return tm;
    }};
  }
  function densifyCum(arr,t0,t1,n){
    if(!arr.length) return arr;
    var s=arr.slice().sort(function(a,b){return a.x-b.x;});
    if(s.length===1) return [{x:t0,y:s[0].y},{x:t1,y:s[0].y}];
    var out=[], steps=Math.max(160, n||320);
    for(var i=0;i<steps;i++){
      var t=t0+(t1-t0)*i/(steps-1);
      var j=0;
      while(j<s.length-1 && s[j+1].x<t) j++;
      if(t<=s[0].x){out.push({x:t,y:s[0].y});continue;}
      if(t>=s[s.length-1].x){out.push({x:t,y:s[s.length-1].y});continue;}
      var a=s[j], b=s[j+1], r=(t-a.x)/(b.x-a.x);
      var y=a.y+(b.y-a.y)*r;
      out.push({x:t,y:y});
    }
    return out;
  }
  async function load(){
    const el=document.getElementById('cf-dli-chart-24h');
    if(!el){setMsg('canvas 없음');return;}
    try{
      const u=API+'?device_id=cronusfarm-01&channels=led_a1,led_b1&hours=48&rolling=1';
      const r=await fetch(u,{credentials:'same-origin'});
      if(!r.ok){setMsg('API '+r.status);return;}
      const j=await r.json();
      const ch=j.channels||{};
      const tEnd=await nowMs();
      const tStart=tEnd-48*3600*1000;
      const a1=integrateCumulative((ch.led_a1||{}).points||[], tStart, tEnd, PPFD);
      const b1=integrateCumulative((ch.led_b1||{}).points||[], tStart, tEnd, PPFD);
      setSum('<span class="a">A Bed 누적 '+a1.total.toFixed(2)+' mol/m²</span><span class="b">B Bed 누적 '+b1.total.toFixed(2)+' mol/m²</span><span class="inst">순간 A '+a1.inst+' · B '+b1.inst+' µmol/m²/s</span>');
      setMsg('우상향 곡선=48h 누적 광량(DLI) · LED OFF 구간은 기울기 0');
      const aS=densifyCum(a1.series,tStart,tEnd,320);
      const bS=densifyCum(b1.series,tStart,tEnd,320);
      const data={datasets:[
        {label:'A Bed 누적',data:aS,borderColor:'#FFD54F',backgroundColor:'rgba(255,213,79,0.28)',borderWidth:2,fill:true,yAxisID:'y',tension:0.42,cubicInterpolationMode:'monotone',stepped:false,pointRadius:0},
        {label:'B Bed 누적',data:bS,borderColor:'#4FC3F7',backgroundColor:'rgba(79,195,247,0.22)',borderWidth:2,fill:true,yAxisID:'y',tension:0.42,cubicInterpolationMode:'monotone',stepped:false,pointRadius:0}
      ]};
      const opt={responsive:true,maintainAspectRatio:false,animation:false,
        elements:{line:{tension:0.42,borderJoinStyle:'round',capBezierPoints:true}},
        interaction:{mode:'index',intersect:false},
        plugins:{legend:{display:true,position:'top',align:'center',labels:{color:'#cfe0f5',boxWidth:10,font:{size:10}}},tooltip:{callbacks:{
          title:function(items){
            if(!items||!items.length||items[0].parsed.x==null||!isFinite(items[0].parsed.x))return '';
            return new Date(items[0].parsed.x).toLocaleString('ko-KR',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});
          },
          label:function(ctx){return ctx.dataset.label+': '+ctx.parsed.y.toFixed(3)+' mol/m²';}
        }}},
        scales:{
          x:{type:'linear',min:tStart,max:tEnd,ticks:cfAxisTicks48h(tStart,tEnd)},
          y:{position:'left',title:{display:true,text:'누적 DLI (mol/m²)',color:'#FFD54F'},ticks:{color:'#FFD54F'},beginAtZero:true}
        }};
      ensureChart(function(){
        if(!chart){chart=new Chart(el.getContext('2d'),{type:'line',data,options:opt});}
        else{chart.config.type='line';chart.data=data;chart.options=opt;chart.update();}
      });
    }catch(e){setMsg('오류: '+e);console.warn(e);}
  }
  setInterval(load,60000);
  setTimeout(load,800);
})(typeof scope!=='undefined'?scope:{ppfd:200});
</script>"""

KMA_CSS_EXTRA = """
    .cf-fe-wide, .cf-fe-wide .cf-fe-frame { overflow: visible !important; max-height: none !important; }
    .cf-fe-kv { grid-template-columns: minmax(4.5em, auto) minmax(5em, 1fr); gap: 6px 10px; }
    .cf-fe-kv .v { white-space: normal; word-break: keep-all; }
    .cf-fe-box-sub { white-space: normal !important; max-width: 55%; line-height: 1.25; }
"""

GAUGE_SPECS = {
    "480e017a1bfbfe7b": ("pH", "pH", "pH", 0, 14),
    "2141fe178c3e2c88": ("EC (µS/cm)", "EC (µS/cm)", "µS/cm", 0, 5000),
    "a0a33715ba8ca5eb": ("TDS (ppm)", "TDS (ppm)", "ppm", 0, 5000),
    "f61aebaa74026feb": ("SALT (‰)", "SALT (‰)", "‰", 0, 50),
    "9d76b919dae993f9": ("S.G", "S.G", "SG", 0, 1.05),
    "1800ba1474d7135c": ("Temp (℃)", "Temp (℃)", "℃", -20, 50),
}


def _ensure_tpl(by: dict, tid: str, name: str, fmt: str, order: int, height: int = 1) -> None:
    """노드가 없을 때만 format 생성. 있으면 order·name만 (layout 패치 format 우선)."""
    n = by.get(tid)
    base = {
        "id": tid,
        "type": "ui_template",
        "z": "tab_cronus_dash",
        "group": "ui_grp_arduino",
        "name": name,
        "order": order,
        "width": "12",
        "height": height,
        "storeOutMessages": False,
        "fwdInMessages": False,
        "resendOnRefresh": True,
        "templateScope": "local",
        "className": "",
        "x": 400,
        "y": 400,
        "wires": [[]],
    }
    if isinstance(n, dict):
        n.update({k: v for k, v in base.items() if k != "format"})
        n["format"] = fmt
        n["storeOutMessages"] = False
        n["fwdInMessages"] = False
    else:
        by[tid] = {**base, "format": fmt}


def main() -> int:
    data = json.loads(DASH.read_text(encoding="utf-8-sig"))
    by = {n["id"]: n for n in data if isinstance(n, dict) and n.get("id")}

    calc = by.get(FN_CALC)
    if calc:
        calc["func"] = FN_CALC_CODE
        calc["outputs"] = 5
        calc["wires"] = [
            [TPL_SUMMARY],
            [TPL_CONN],
            [TPL_USB],
            [TPL_MQTT],
            [TPL_R3],
        ]

    seen = by.get(FN_SEEN_TELE)
    if seen:
        seen["func"] = FN_SEEN_TELE_CODE

    seen_st = by.get("fn_seen_status")
    if seen_st:
        w = seen_st.get("wires") or [[]]
        outs = list(w[0]) if w else []
        if "fn_calc_online" in outs:
            seen_st["wires"] = [[x for x in outs if x != "fn_calc_online"]]

    _ensure_tpl(by, TPL_SUMMARY, "farm 제어 경로", _FMT_SUMMARY, 2, height=2)
    _ensure_tpl(by, TPL_CONN, "R4 WiFi (디바이스)", _FMT_CONN, 3)
    _ensure_tpl(by, TPL_USB, "farm primary (USB)", _FMT_USB, 4)
    _ensure_tpl(by, TPL_MQTT, "farm 백업 (WiFi MQTT)", _FMT_MQTT, 5)
    _ensure_tpl(by, TPL_R3, "R3 패널 (I2C)", _FMT_R3, 6)

    arduino_grp = by.get("ui_grp_arduino")
    if arduino_grp:
        arduino_grp["name"] = "Arduino (R4 · R3)"

    gh = by.get(GH_GROUP)
    if gh:
        gh["name"] = "양액 상태 Data"
    for gid, (name, title, label, mn, mx) in GAUGE_SPECS.items():
        g = by.get(gid)
        if isinstance(g, dict):
            g["name"] = name
            g["title"] = title
            g["label"] = label
            g["min"] = mn
            g["max"] = mx
            g["group"] = GH_GROUP

    farm = by.get(TPL_FARM)
    if farm:
        fmt = farm.get("format") or ""
        if "cf-fe-wide" in fmt and "overflow: visible" not in fmt:
            fmt = fmt.replace("</style>", KMA_CSS_EXTRA + "\n  </style>", 1)
            farm["format"] = fmt

    by[TPL_DLI] = {
        "id": TPL_DLI,
        "type": "ui_template",
        "z": "tab_cronus_dash",
        "group": GH_GROUP,
        "name": "LED 누적 광량 (48h)",
        "order": 5,
        "width": "12",
        "height": 7,
        "format": DLI_CHART_FMT,
        "storeOutMessages": True,
        "fwdInMessages": False,
        "resendOnRefresh": True,
        "templateScope": "local",
        "className": "",
        "x": 400,
        "y": 980,
        "wires": [[]],
    }
    if CHART_PHW in by:
        by[CHART_PHW]["order"] = 4

    id_set = {x.get("id") for x in data if isinstance(x, dict)}
    for i, n in enumerate(data):
        if isinstance(n, dict) and n.get("id") in by:
            data[i] = by[n["id"]]
    for nid, node in by.items():
        if nid not in id_set:
            data.append(node)
    DASH.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print("OK patch_dashboard_monitor_extended")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
