# -*- coding: utf-8 -*-
"""flows_cronusfarm_dashboard.json 에 텔레그램 전송 테스트(GET /farm/cronusfarm/telegram-ping) 추가.

환경변수( Node-RED 프로세스에 설정 ):
  CRONUSFARM_TELEGRAM_BOT_TOKEN — BotFather 토큰
  CRONUSFARM_TELEGRAM_CHAT_ID   — 숫자 chat id

선택 쿼리: ?text=메시지내용 (미지정 시 기본 문구)
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

FN_PREP = """const token = (env.get('CRONUSFARM_TELEGRAM_BOT_TOKEN') || '').toString().trim();
const chat = (env.get('CRONUSFARM_TELEGRAM_CHAT_ID') || '').toString().trim();
const q = (msg.req && msg.req.query) ? msg.req.query : {};
let text = 'CronusFarm Telegram ping OK';
if (q.text != null && String(q.text).length > 0) {
  text = String(q.text);
}
if (!token || !chat) {
  msg.statusCode = 500;
  msg.headers = { 'Content-Type': 'application/json; charset=utf-8' };
  msg.payload = JSON.stringify({
    ok: false,
    error: 'Missing CRONUSFARM_TELEGRAM_BOT_TOKEN or CRONUSFARM_TELEGRAM_CHAT_ID'
  });
  return [null, msg];
}
msg.method = 'GET';
msg.url = 'https://api.telegram.org/bot' + token + '/sendMessage?chat_id=' + encodeURIComponent(chat) + '&text=' + encodeURIComponent(text);
return [msg, null];"""

FN_WRAP = """msg.statusCode = msg.statusCode || 200;
msg.headers = Object.assign({}, msg.headers || {}, { 'Content-Type': 'application/json; charset=utf-8' });
if (typeof msg.payload !== 'string') {
  try { msg.payload = JSON.stringify(msg.payload); } catch (e) { msg.payload = String(msg.payload); }
}
return msg;"""

NODES = [
    {
        "id": "cf_hin_tg_ping",
        "type": "http in",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "텔레그램 ping GET",
        "url": "/farm/cronusfarm/telegram-ping",
        "method": "get",
        "upload": False,
        "swaggerDoc": "",
        "x": 130,
        "y": 820,
        "wires": [["cf_fn_tg_prep"]],
    },
    {
        "id": "cf_fn_tg_prep",
        "type": "function",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "→ Telegram sendMessage",
        "func": FN_PREP,
        "outputs": 2,
        "noerr": 0,
        "initialize": "",
        "finalize": "",
        "libs": [],
        "x": 360,
        "y": 820,
        "wires": [["cf_hreq_tg"], ["cf_hres_tg_err"]],
    },
    {
        "id": "cf_hreq_tg",
        "type": "http request",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "Telegram API",
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
        "x": 580,
        "y": 810,
        "wires": [["cf_fn_tg_wrap"]],
    },
    {
        "id": "cf_fn_tg_wrap",
        "type": "function",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "응답 헤더",
        "func": FN_WRAP,
        "outputs": 1,
        "noerr": 0,
        "initialize": "",
        "finalize": "",
        "libs": [],
        "x": 700,
        "y": 810,
        "wires": [["cf_hres_tg_ok"]],
    },
    {
        "id": "cf_hres_tg_ok",
        "type": "http response",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "Telegram 응답(성공)",
        "statusCode": "",
        "headers": {},
        "x": 880,
        "y": 810,
        "wires": [],
    },
    {
        "id": "cf_hres_tg_err",
        "type": "http response",
        "z": "b1c5a1f1d7a2a3a1",
        "name": "Telegram 응답(env 없음)",
        "statusCode": "",
        "headers": {},
        "x": 580,
        "y": 860,
        "wires": [],
    },
]


def main() -> None:
    flows = json.loads(FLOW.read_text(encoding="utf-8"))
    ids = {n.get("id") for n in flows if isinstance(n, dict)}
    if "cf_hin_tg_ping" in ids:
        print("skip: telegram ping nodes already present")
        return
    flows.extend(NODES)
    FLOW.write_text(json.dumps(flows, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    print(f"OK appended telegram ping to {FLOW}")


if __name__ == "__main__":
    main()
