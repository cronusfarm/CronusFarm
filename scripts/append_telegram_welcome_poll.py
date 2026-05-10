# -*- coding: utf-8 -*-
"""flows_cronusfarm_dashboard.json 에 텔레그램 환영·관심사 안내 폴링(getUpdates) 플로우 추가.

- 주기적으로 getUpdates 호출(짧은 폴링)
- /start·/help: 환영 안내만
- 날씨: Open-Meteo 현재값(기온/습도/강수/상태) + 간단 브리핑
- 그 외 모든 텍스트: 키워드별 답변(대화 상태 저장 없음 — 배포 후에도 동작 일관)
- 토큰: CRONUSFARM_TELEGRAM_BOT_TOKEN (필수). CHAT_ID 불필요.
  - 날씨 위치: CRONUSFARM_WEATHER_LAT / CRONUSFARM_WEATHER_LON / (선택) CRONUSFARM_WEATHER_NAME

중복 추가 방지: cf_inj_tg_welcome 존재 시 skip
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
TAB = "b1c5a1f1d7a2a3a1"

FN_POLL = r"""const token = (env.get('CRONUSFARM_TELEGRAM_BOT_TOKEN') || '').toString().trim();
if (!token) { return null; }
const off = global.get('cfTgPollOffset') || 0;
msg.method = 'GET';
msg.url = 'https://api.telegram.org/bot' + token + '/getUpdates?offset=' + encodeURIComponent(String(off)) + '&timeout=0';
return msg;"""

# node.send 으로 답장만 분기; return null
FN_DISPATCH = r"""const token = (env.get('CRONUSFARM_TELEGRAM_BOT_TOKEN') || '').toString().trim();
if (!token) { return null; }
let raw = msg.payload;
if (typeof raw === 'object') { raw = JSON.stringify(raw); }
let data;
try { data = JSON.parse(raw); } catch (e) { return null; }
if (!data || !data.ok) { return null; }
const updates = data.result || [];
if (!updates.length) { return null; }

let off = global.get('cfTgPollOffset') || 0;
const WELCOME = '안녕하세요! CronusFarm 봇입니다.\n\n궁금하신 내용을 키워드로 보내 주세요.\n(예: 스케줄, 센서, 날씨, 급수, LED, 환기, 알림, 대시보드, 아두이노)\n\n이 안내 다시 보기: /start';

function mkSend(chatId, text) {
  return {
    method: 'POST',
    url: 'https://api.telegram.org/bot' + token + '/sendMessage',
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
    payload: JSON.stringify({ chat_id: Number(chatId), text: text })
  };
}

function matchInterest(t) {
  const s = String(t || '').toLowerCase();
  if (/스케줄|시간|타이머|주기/.test(s)) {
    return '스케줄은 Node-RED와 SQLite 브리지에서 다룹니다. 대시보드의 "스케줄 변경하기"에서 장치·요일·구간·주기를 설정할 수 있어요.';
  }
  if (/급수|관수|물주|펌프|pump|물탱크/.test(s)) {
    return '급수·펌프는 MQTT cmd 로 채널 제어하고, tele 로 상태를 받는 구조입니다. 스케줄·수동은 대시보드와 스케줄 규칙에서 맞추면 됩니다.';
  }
  if (/led|조명|빛|광량|생장등|배광/.test(s)) {
    return '조명·LED 채널은 펌웨어 핀·MQTT cmd 매핑에 따릅니다. 대시보드에서 채널 ON/OFF·스케줄과 연동해 쓸 수 있어요.';
  }
  if (/환기|팬|\bfan\b|송풍/.test(s)) {
    return '환기·팬도 MQTT cmd/tele 로 제어·상태 확인합니다. Bed·채널별로 UI와 스케줄을 맞춰 두면 됩니다.';
  }
  if (/배양액|ec|ph|비료|영양|전도도/.test(s)) {
    return '배양액·EC/pH 등은 센서가 tele 로 올리면 SQLite/Influx에 쌓고, 임계 알림은 Node-RED 조건으로 걸 수 있습니다. 센서·캘리브레이션은 현장 장비 매뉴얼을 따르세요.';
  }
  if (/병해|해충|곰팡이|작물병/.test(s)) {
    return '병해충 판별은 전문 앱·전문가 상담을 권장합니다. CronusFarm은 환경(온습도·급수 등) 기록·알림에 초점을 둡니다.';
  }
  if (/wifi|와이파이|네트워크|tailscale|ssh|ip\s*주소/.test(s)) {
    return 'Pi는 LAN·Tailscale(예: ida…ts.net) 등으로 접속합니다. Arduino secrets.h 의 MQTT_HOST 와 PC 배포 스크립트의 Pi 주소를 같은 호스트로 맞추면 됩니다.';
  }
  if (/설치|배포|업데이트|\bgit\b|클론|동기화/.test(s)) {
    return '저장소는 Git 으로 관리하고, Windows 에서 deploy-cronusfarm-pi.ps1 로 Pi에 Node-RED·스크립트를 올립니다. Pi 상세는 docs/raspi_setup.md 를 보세요.';
  }
  if (/온실|하우스|비닐하우스|greenhouse|농장\s*운영/.test(s)) {
    return '온실 운영은 스케줄·센서·액추에이터를 한 흐름으로 묶는 것이 핵심입니다. CronusFarm은 Bed·채널 단위 제어와 기록을 지향합니다.';
  }
  if (/센서|온도|습도|\btele\b|mqtt|토픽/.test(s)) {
    return '센서·상태는 MQTT(tele/status 등)로 Pi에 전달되고, SQLite·Influx·Grafana에서 확인할 수 있습니다. DEVICE_ID 는 토픽 cronusfarm/<ID>/… 에 맞춥니다.';
  }
  if (/알림|알람|텔레그램|telegram|메시지/.test(s)) {
    return '이 봇으로 알림을 보낼 수 있도록 플로우가 준비되어 있습니다. 임계 초과·이벤트 발생 시 sendMessage 로 연결하면 됩니다.';
  }
  if (/노드|node-red|노드레드|플로우/.test(s)) {
    return 'Node-RED는 라즈베리파이에서 돌아갑니다. 저장소 nodered/ 플로우를 병합·배포하면 Pi에 반영됩니다.';
  }
  if (/대시보드|grafana|그라파나|nrdb|\/ui/.test(s)) {
    return '화면은 FlowFuse Dashboard(/nrdb2 등)와 Grafana(선택)로 볼 수 있습니다. 브라우저에서 Pi 주소:1880 으로 접속해 보세요.';
  }
  if (/arduino|아두이노|펌웨어|uno|r4|스케치/.test(s)) {
    return '아두이노(UNO R4 WiFi)는 MQTT로 Pi와 통신합니다. 스케치는 arduino/CronusFarm/ 이고, PC에서 upcode 로 Pi에 올린 뒤 업로드합니다.';
  }
  if (/카메라|영상|rtsp|ai|ollama|llm/.test(s)) {
    return '카메라·AI는 RTSP/추론 서비스와 연동하고, Node-RED는 결과 저장·알림 역할을 맡는 구조를 권장합니다. 문서 Edge AI(준비) 절을 참고하세요.';
  }
  if (/sqlite|db|데이터베이스|기록/.test(s)) {
    return '정합·마스터 기록은 SQLite(cronusfarm.sqlite), 시계열 시각화는 Influx·Grafana 경로를 씁니다. 브리지 HTTP API 로도 조회·저장할 수 있어요.';
  }
  return 'CronusFarm은 스마트팜 제어(MQTT·스케줄·기록·알림)를 한 저장소에서 관리하는 프로젝트입니다.\n날씨·급수·LED·환기·네트워크 같은 단어로도 질문해 보세요.\n처음 안내: /start';
}

const proc = global.get('cfTgProcIds') || {};
const out1 = [];
const out2 = [];

for (let i = 0; i < updates.length; i++) {
  const u = updates[i];
  const uid = u.update_id;
  if (proc[uid]) { continue; }
  proc[uid] = 1;
  const pk = Object.keys(proc);
  if (pk.length > 500) {
    pk.map(Number).sort((a, b) => a - b).slice(0, pk.length - 400).forEach((k) => { delete proc[k]; });
  }
  if (uid >= off) { off = uid + 1; }
  const m = u.message;
  if (!m || !m.chat || !m.chat.id) { continue; }
  if (m.from && m.from.is_bot) { continue; }
  const cid = String(m.chat.id);
  const text = String(m.text || '').trim();
  const low = text.toLowerCase();

  if (text === '/start' || text === '/help' || low === '시작' || low === '도움' || low === 'help') {
    out1.push(mkSend(cid, WELCOME));
    continue;
  }
  if (text.length === 0) {
    out1.push(mkSend(cid, '텍스트로 질문해 주세요. 안내: /start'));
    continue;
  }

  // 날씨는 별도 HTTP 요청 분기
  if (/날씨|기상|예보|\bweather\b|외부온도|강수|바람/.test(low)) {
    out2.push({ chat_id: Number(cid), ask_text: text });
  } else {
    out1.push(mkSend(cid, matchInterest(text) + '\n\n— 다른 주제: 키워드로 다시 보내기 또는 /start'));
  }
}

global.set('cfTgProcIds', proc);
global.set('cfTgPollOffset', off);
return [out1, out2];"""

FN_WEATHER_URL = r"""const lat = (env.get('CRONUSFARM_WEATHER_LAT') || '').toString().trim();
const lon = (env.get('CRONUSFARM_WEATHER_LON') || '').toString().trim();
const name = (env.get('CRONUSFARM_WEATHER_NAME') || '').toString().trim();
if (!lat || !lon) {
  msg.method = 'POST';
  msg.url = 'https://api.telegram.org/bot' + (env.get('CRONUSFARM_TELEGRAM_BOT_TOKEN') || '') + '/sendMessage';
  msg.headers = { 'Content-Type': 'application/json; charset=utf-8' };
  msg.payload = JSON.stringify({
    chat_id: Number(msg.chat_id),
    text: '날씨 위치가 설정되어 있지 않습니다.\\nPi의 /etc/cronusfarm/nodered-telegram.env 에\\nCRONUSFARM_WEATHER_LAT / CRONUSFARM_WEATHER_LON 을 넣어 주세요.'
  });
  return [null, msg];
}
msg._cf_weather_name = name;
msg._cf_chat_id = Number(msg.chat_id);
msg.method = 'GET';
msg.url = 'https://api.open-meteo.com/v1/forecast'
  + '?latitude=' + encodeURIComponent(lat)
  + '&longitude=' + encodeURIComponent(lon)
  + '&current=temperature_2m,relative_humidity_2m,precipitation,weather_code'
  + '&hourly=precipitation'
  + '&forecast_days=1'
  + '&timezone=Asia%2FSeoul';
return [msg, null];"""

FN_WEATHER_FMT = r"""function kstNow() {
  const d = new Date(Date.now() + 9*60*60*1000);
  const mm = String(d.getUTCMonth()+1).padStart(2,'0');
  const dd = String(d.getUTCDate()).padStart(2,'0');
  return { mm, dd, h: d.getUTCHours() };
}
function wdesc(code) {
  const c = Number(code);
  const m = {
    0:['맑음','🌤️'],
    1:['대체로 맑음','🌤️'],
    2:['구름 조금','⛅'],
    3:['흐림','☁️'],
    45:['안개','🌫️'],48:['안개','🌫️'],
    51:['이슬비','🌦️'],53:['이슬비','🌦️'],55:['이슬비','🌦️'],
    61:['비','🌧️'],63:['비','🌧️'],65:['강한 비','🌧️'],
    71:['눈','🌨️'],73:['눈','🌨️'],75:['강한 눈','🌨️'],
    80:['소나기','🌦️'],81:['소나기','🌦️'],82:['강한 소나기','🌧️'],
    95:['뇌우','⛈️'],96:['뇌우+우박','⛈️'],99:['뇌우+우박','⛈️'],
  };
  return m[c] || ['날씨','🌤️'];
}

let raw = msg.payload;
if (typeof raw === 'object') { raw = JSON.stringify(raw); }
let data;
try { data = JSON.parse(raw); } catch (e) { data = null; }
if (!data || !data.current) { return null; }

const cur = data.current;
const t = Number(cur.temperature_2m);
const h = Number(cur.relative_humidity_2m);
const p = Number(cur.precipitation);
const wc = cur.weather_code;
const wd = wdesc(wc);
const now = kstNow();
const title = `🌞 ${now.mm}월 ${now.dd}일 농업 정보` + (msg._cf_weather_name ? ` (${msg._cf_weather_name})` : '');

// 1시간 강수는 hourly[현재시간] 근사
let p1 = 0;
try {
  const idx = Math.max(0, Math.min((data.hourly && data.hourly.precipitation ? data.hourly.precipitation.length-1 : 0), Number(now.h)));
  p1 = Number(data.hourly.precipitation[idx] || 0);
} catch (e) {}

const lines = [];
lines.push(title);
lines.push('');
lines.push(`${wd[1]} 날씨: ${wd[0]} | 🌡️ 현재 기온: ${t.toFixed(1)}°C | 💧 습도: ${Math.round(h)}% | ☔ 1시간 강수: ${p1.toFixed(1)}mm`);
lines.push('');
lines.push('📋 개인화 브리핑:');

const tips = [];
if (h <= 40) tips.push(`1. 습도 관리: 현재 습도가 낮은 편(${Math.round(h)}%)이므로, 작물 목표에 맞게 습도를 올리는 것을 고려하세요(분무/가습/관수 타이밍 조정).`);
else if (h >= 80) tips.push(`1. 습도 관리: 습도가 높은 편(${Math.round(h)}%)입니다. 결로·병해 위험이 있어 환기/제습을 점검하세요.`);
else tips.push(`1. 습도 관리: 습도는 ${Math.round(h)}%로 중간 수준입니다. 목표 범위 유지에 집중하세요.`);

if (t >= 30) tips.push(`2. 온도 조절: 기온이 높습니다(${t.toFixed(1)}°C). 차광·환기·냉방 준비를 권장합니다.`);
else if (t <= 5) tips.push(`2. 온도 조절: 기온이 낮습니다(${t.toFixed(1)}°C). 난방·보온 상태를 확인하세요.`);
else tips.push(`2. 온도 조절: 기온은 ${t.toFixed(1)}°C 입니다. 센서 추세를 보며 오후/야간 대비를 하세요.`);

if (p1 > 0.0 || p > 0.0) tips.push(`3. 강수/환기: 강수 영향이 있습니다(최근/현재). 외기 유입·환기 전략을 조정하고, 누수·배수 상태를 확인하세요.`);
else tips.push(`3. 병해충 예방: 건조/환기 조건에 따라 병해 발생이 달라집니다. 정기 점검으로 초기 증상을 빠르게 확인하세요.`);

lines.push(...tips);
lines.push('');
lines.push('━━━━━━━━━━━━━━━━');

msg.method = 'POST';
msg.url = 'https://api.telegram.org/bot' + (env.get('CRONUSFARM_TELEGRAM_BOT_TOKEN') || '') + '/sendMessage';
msg.headers = { 'Content-Type': 'application/json; charset=utf-8' };
msg.payload = JSON.stringify({ chat_id: Number(msg._cf_chat_id), text: lines.join('\\n') });
return msg;"""

NODES = [
    {
        "id": "cf_inj_tg_welcome",
        "type": "inject",
        "z": TAB,
        "name": "텔레그램 수신 폴링",
        "props": [{"p": "payload"}],
        "repeat": "8",
        "crontab": "",
        "once": False,
        "onceDelay": 0.5,
        "topic": "",
        "payload": "",
        "payloadType": "date",
        "x": 130,
        "y": 920,
        "wires": [["cf_fn_tg_pollurl"]],
    },
    {
        "id": "cf_fn_tg_pollurl",
        "type": "function",
        "z": TAB,
        "name": "getUpdates URL",
        "func": FN_POLL,
        "outputs": 1,
        "timeout": 0,
        "noerr": 0,
        "initialize": "",
        "finalize": "",
        "libs": [],
        "x": 320,
        "y": 920,
        "wires": [["cf_hreq_tg_getup"]],
    },
    {
        "id": "cf_hreq_tg_getup",
        "type": "http request",
        "z": TAB,
        "name": "Telegram getUpdates",
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
        "y": 920,
        "wires": [["cf_fn_tg_dispatch"]],
    },
    {
        "id": "cf_fn_tg_dispatch",
        "type": "function",
        "z": TAB,
        "name": "환영·관심사 분기",
        "func": FN_DISPATCH,
        "outputs": 1,
        "timeout": 0,
        "noerr": 0,
        "initialize": "",
        "finalize": "",
        "libs": [],
        "x": 720,
        "y": 920,
        "wires": [["cf_hreq_tg_sendmsg"]],
    },
    {
        "id": "cf_hreq_tg_sendmsg",
        "type": "http request",
        "z": TAB,
        "name": "Telegram sendMessage",
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
        "x": 940,
        "y": 920,
        "wires": [[]],
    },
]


def main() -> None:
    flows = json.loads(FLOW.read_text(encoding="utf-8"))
    ids = {n.get("id") for n in flows if isinstance(n, dict)}
    if "cf_inj_tg_welcome" in ids:
        print("skip: welcome poll nodes already present")
        return
    flows.extend(NODES)
    FLOW.write_text(json.dumps(flows, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    print(f"OK appended telegram welcome poll to {FLOW}")


if __name__ == "__main__":
    main()
