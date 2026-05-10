# -*- coding: utf-8 -*-
"""flows_cronusfarm_dashboard.json 에 텔레그램 "오늘의 CronusFarm News" 일일 발송 노드 추가.

- 매일 오전 09:00(KST, Node-RED 호스트 타임존 기준) 자동 발송
- 수동 inject 버튼으로 즉시 테스트 발송 가능
- 토큰/채팅ID는 환경변수 사용:
  - CRONUSFARM_TELEGRAM_BOT_TOKEN
  - CRONUSFARM_TELEGRAM_CHAT_ID

중복 추가 방지: cf_inj_tg_news_daily 존재 시 skip
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
TAB = "b1c5a1f1d7a2a3a1"

FN_PREP = """const token = (env.get('CRONUSFARM_TELEGRAM_BOT_TOKEN') || '').toString().trim();
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

const nowTs = fmtKst(Date.now());
const teleTs = fmtKst(flow.get('arduinoLastTeleMs'));
const statusTs = fmtKst(flow.get('arduinoLastStatusMs'));
const gState = (flow.get('lastTeleG') || '').toString().trim() || '미수신';
const lastTele = (flow.get('lastTeleStr') || '').toString().trim();
const telePreview = lastTele ? lastTele.slice(0, 120) : '미수신';
const now = new Date(Date.now() + 9 * 60 * 60 * 1000);
const mon = String(now.getUTCMonth() + 1).padStart(2, '0');
const day = String(now.getUTCDate()).padStart(2, '0');

// KMA 스냅샷은 아직 flow context에 명시 저장 노드가 없어, 있으면 사용하고 없으면 미수신으로 표기
const kma = flow.get('kmaSnapshot') || global.get('kmaSnapshot') || {};
const temp = (kma.kma_temp ?? '미수신');
const hum = (kma.kma_humidity ?? '미수신');
const ptyRaw = (kma.kma_precip_type ?? '');
const pcp = (kma.kma_precip_1h ?? '미수신');
const ptyMap = { '0': '없음', '1': '비', '2': '비/눈', '3': '눈', '4': '소나기' };
const pty = (ptyRaw === '' || ptyRaw == null) ? '미수신' : (ptyMap[String(ptyRaw)] || String(ptyRaw));

const text =
`🌙 ${mon}월 ${day}일 저녁 영농 준비

🌤️ 날씨: 🌡️ 현재 기온: ${temp}${temp === '미수신' ? '' : '°C'}  |  💧 습도: ${hum}${hum === '미수신' ? '' : '%'}  |  🌧️ 강수형태: ${pty}  |  ☔ 1시간 강수: ${pcp}${pcp === '미수신' ? '' : 'mm'}

📡 MQTT 수집 상태
• tele 마지막 수신: ${teleTs}
• status 마지막 수신: ${statusTs}
• 펌프가드(G) 상태: ${gState}
• tele 미리보기: ${telePreview}

📋 CronusFarm 브리핑:
• 오늘 저녁: tele/status 수신 지속 여부와 펌프가드(G) 상태를 먼저 점검해 주세요.
• 내일 준비: 스케줄/수동 제어 값(on/off, auto_*)이 의도대로 유지되는지 확인해 주세요.
• pH/EC/수온, CCTV/SAM은 아직 미연동·미구현이며, 임의 수치는 전송하지 않습니다.`;
msg.method = 'POST';
msg.url = 'https://api.telegram.org/bot' + token + '/sendMessage';
msg.headers = { 'Content-Type': 'application/json; charset=utf-8' };
msg.payload = JSON.stringify({ chat_id: Number(chat), text: text });
return msg;"""

NODES = [
    {
        "id": "cf_inj_tg_news_daily",
        "type": "inject",
        "z": TAB,
        "name": "텔레그램 뉴스(매일 09:00)",
        "props": [{"p": "payload"}],
        "repeat": "",
        "crontab": "0 9 * * *",
        "once": False,
        "onceDelay": 0.1,
        "topic": "",
        "payload": "",
        "payloadType": "date",
        "x": 130,
        "y": 980,
        "wires": [["cf_fn_tg_news_daily"]],
    },
    {
        "id": "cf_inj_tg_news_now",
        "type": "inject",
        "z": TAB,
        "name": "텔레그램 뉴스(지금 테스트)",
        "props": [{"p": "payload"}],
        "repeat": "",
        "crontab": "",
        "once": False,
        "onceDelay": 0.1,
        "topic": "",
        "payload": "",
        "payloadType": "date",
        "x": 130,
        "y": 1020,
        "wires": [["cf_fn_tg_news_daily"]],
    },
    {
        "id": "cf_fn_tg_news_daily",
        "type": "function",
        "z": TAB,
        "name": "뉴스 메시지 준비",
        "func": FN_PREP,
        "outputs": 1,
        "timeout": 0,
        "noerr": 0,
        "initialize": "",
        "finalize": "",
        "libs": [],
        "x": 350,
        "y": 1000,
        "wires": [["cf_hreq_tg_sendmsg"]],
    },
]


def main() -> None:
    flows = json.loads(FLOW.read_text(encoding="utf-8"))
    ids = {n.get("id") for n in flows if isinstance(n, dict)}
    if "cf_inj_tg_news_daily" in ids:
        print("skip: telegram daily news nodes already present")
        return
    flows.extend(NODES)
    FLOW.write_text(json.dumps(flows, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    print(f"OK appended telegram daily news to {FLOW}")


if __name__ == "__main__":
    main()
