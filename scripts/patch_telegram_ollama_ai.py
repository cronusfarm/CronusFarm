# -*- coding: utf-8 -*-
"""텔레그램 수신 → Ollama(gemma:2b) AI 답변 분기 추가."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAB = "b1c5a1f1d7a2a3a1"

FN_DISPATCH = r"""const token = (env.get('CRONUSFARM_TELEGRAM_BOT_TOKEN') || '').toString().trim();
const aiOn = (env.get('CRONUSFARM_OLLAMA_ENABLED') || '1').toString().trim() !== '0';
if (!token) { return null; }
let raw = msg.payload;
if (typeof raw === 'object') { raw = JSON.stringify(raw); }
let data;
try { data = JSON.parse(raw); } catch (e) { return null; }
if (!data || !data.ok) { return null; }
const updates = data.result || [];
if (!updates.length) { return null; }

let off = global.get('cfTgPollOffset') || 0;
const WELCOME = '안녕하세요! CronusFarm AI 봇입니다.\n\n질문을 보내 주시면 농장 데이터(KMA·PHW·CCTV·MQTT)를 참고해 답합니다.\n날씨 키워드: 날씨 / 기상 / 예보\n안내: /start';

function mkSend(chatId, text) {
  return {
    method: 'POST',
    url: 'https://api.telegram.org/bot' + token + '/sendMessage',
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
    payload: JSON.stringify({ chat_id: Number(chatId), text: text })
  };
}

const proc = global.get('cfTgProcIds') || {};
const out1 = [];
const out2 = [];
const out3 = [];

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
    out1.push(mkSend(cid, '텍스트로 질문해 주세요. /start'));
    continue;
  }
  if (/날씨|기상|예보|\bweather\b|외부온도|강수|바람/.test(low)) {
    out2.push({ chat_id: Number(cid), ask_text: text });
    continue;
  }
  if (aiOn) {
    out3.push({ chat_id: Number(cid), ask_text: text });
    continue;
  }
  out1.push(mkSend(cid, 'AI 비활성(CRONUSFARM_OLLAMA_ENABLED=0). /start'));
}

global.set('cfTgProcIds', proc);
global.set('cfTgPollOffset', off);
return [out1, out2, out3];"""

FN_OLLAMA_BUILD = r"""const model = (env.get('CRONUSFARM_OLLAMA_MODEL') || 'gemma:2b').toString().trim();
const host = (env.get('CRONUSFARM_OLLAMA_HOST') || 'http://127.0.0.1:11434').toString().replace(/\/$/, '');
const kma = global.get('kmaSnapshot') || flow.get('kmaSnapshot') || {};
const phw = global.get('phwSnapshot') || flow.get('phwSnapshot') || {};
const ai = global.get('cameraAiSnapshot') || flow.get('cameraAiSnapshot') || {};
const teleMs = flow.get('arduinoLastTeleMs');
const q = (msg.ask_text || '').toString().trim();

function ptyLabel(k) {
  const p = k.kma_precip_type ?? k.kma_pty;
  const m = { '0': '없음', '1': '비', '2': '비/눈', '3': '눈', '4': '소나기' };
  let s = (p === null || p === undefined || p === '') ? '미수신' : (m[String(p)] || String(p));
  const rn = Number(k.kma_precip_1h);
  if ((s === '없음' || s === '미수신') && Number.isFinite(rn) && rn > 0) s = '강우';
  return s;
}

const ctx = [
  '농장: 서울 강동구 천호동 (천호대로151길 36)',
  `KMA: 기온 ${kma.kma_temp ?? '—'}°C, 습도 ${kma.kma_humidity ?? '—'}%, 강수 ${ptyLabel(kma)}, 1h ${kma.kma_precip_1h ?? '—'}mm`,
  `PHW3988: pH ${phw.ph ?? '—'}, EC ${phw.ec ?? '—'} µS/cm, 수온 ${phw.temp_c ?? '—'}°C`,
  `CCTV: ${ai.count ?? '—'}개 — ${(ai.caption || '—').toString().slice(0, 80)}`,
  `Arduino tele: ${teleMs ? '최근 수신' : '미수신'}`
].join('\n');

const prompt = `당신은 CronusFarm 스마트팜 운영 도우미입니다. 아래 [현장 데이터]만 근거로 한국어로 답하세요. 모르면 모른다고 하세요. 400자 이내.\n\n[현장 데이터]\n${ctx}\n\n[질문]\n${q}`;

msg._cf_chat_id = Number(msg.chat_id);
msg.method = 'POST';
msg.url = host + '/api/generate';
msg.headers = { 'Content-Type': 'application/json' };
msg.payload = JSON.stringify({ model, prompt, stream: false, options: { num_predict: 420, temperature: 0.4 } });
return msg;"""

FN_OLLAMA_REPLY = r"""const token = (env.get('CRONUSFARM_TELEGRAM_BOT_TOKEN') || '').toString().trim();
if (!token) { return null; }
let raw = msg.payload;
if (typeof raw === 'object') { raw = JSON.stringify(raw); }
let data;
try { data = JSON.parse(raw); } catch (e) {
  data = null;
}
let ans = 'AI 응답을 처리하지 못했습니다.';
if (data && data.response) {
  ans = String(data.response).trim();
} else if (data && data.error) {
  ans = 'Ollama 오류: ' + String(data.error);
}
if (ans.length > 3500) ans = ans.slice(0, 3500) + '…';
msg.method = 'POST';
msg.url = 'https://api.telegram.org/bot' + token + '/sendMessage';
msg.headers = { 'Content-Type': 'application/json; charset=utf-8' };
msg.payload = JSON.stringify({ chat_id: Number(msg._cf_chat_id), text: ans });
return msg;"""


def patch_flow(path: Path) -> None:
    if not path.is_file():
        return
    flows = json.loads(path.read_text(encoding="utf-8-sig"))
    ids = {n.get("id") for n in flows if isinstance(n, dict)}

    for n in flows:
        if not isinstance(n, dict):
            continue
        if n.get("id") == "cf_fn_tg_dispatch":
            n["func"] = FN_DISPATCH
            n["outputs"] = 3
            n["wires"] = [
                ["cf_hreq_tg_sendmsg"],
                ["cf_fn_tg_weather_url"],
                ["cf_fn_tg_ollama_build"],
            ]

    def upsert(node: dict) -> None:
        nid = node["id"]
        for i, n in enumerate(flows):
            if isinstance(n, dict) and n.get("id") == nid:
                flows[i] = {**n, **node}
                return
        flows.append(node)
        ids.add(nid)

    if "cf_fn_tg_ollama_build" not in ids:
        upsert(
            {
                "id": "cf_fn_tg_ollama_build",
                "type": "function",
                "z": TAB,
                "name": "Ollama 요청",
                "func": FN_OLLAMA_BUILD,
                "outputs": 1,
                "timeout": 120,
                "noerr": 0,
                "initialize": "",
                "finalize": "",
                "libs": [],
                "x": 960,
                "y": 1000,
                "wires": [["cf_hreq_tg_ollama"]],
            }
        )
        upsert(
            {
                "id": "cf_hreq_tg_ollama",
                "type": "http request",
                "z": TAB,
                "name": "Ollama generate",
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
                "x": 1180,
                "y": 1000,
                "wires": [["cf_fn_tg_ollama_reply"]],
            }
        )
        upsert(
            {
                "id": "cf_fn_tg_ollama_reply",
                "type": "function",
                "z": TAB,
                "name": "Ollama→Telegram",
                "func": FN_OLLAMA_REPLY,
                "outputs": 1,
                "timeout": 0,
                "noerr": 0,
                "initialize": "",
                "finalize": "",
                "libs": [],
                "x": 1400,
                "y": 1000,
                "wires": [["cf_hreq_tg_sendmsg"]],
            }
        )

    path.write_text(json.dumps(flows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("OK", path.name)


def main() -> None:
    for name in (
        "flows_cronusfarm_dashboard.json",
        "flows_cronusfarm_mqtt.json",
        "CronusFarm_NodeRED_flow.json",
    ):
        patch_flow(ROOT / "nodered" / name)


if __name__ == "__main__":
    main()
