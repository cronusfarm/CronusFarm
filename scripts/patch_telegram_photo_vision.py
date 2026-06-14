# -*- coding: utf-8 -*-
"""텔레그램 사진 → cronusfarm_telegram_vision.py (Gemini/OpenAI/Ollama).

- cf_fn_tg_dispatch: outputs=4 (0=즉시답, 1=날씨, 2=Ollama, 3=사진비전)
- cf_fn_tg_photo_run: python3 --file-id --chat-id --send
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAB = "b1c5a1f1d7a2a3a1"

FN_DISPATCH = r"""const token = (env.get('CRONUSFARM_TELEGRAM_BOT_TOKEN') || '').toString().trim();
const aiOn = (env.get('CRONUSFARM_OLLAMA_ENABLED') || '1').toString().trim() !== '0';
const visionOn = (env.get('CRONUSFARM_VISION_ENABLED') || '1').toString().trim() !== '0';
if (!token) { return null; }
let raw = msg.payload;
if (typeof raw === 'object') { raw = JSON.stringify(raw); }
let data;
try { data = JSON.parse(raw); } catch (e) { return null; }
if (!data || !data.ok) { return null; }
const updates = data.result || [];
if (!updates.length) { return null; }

let off = global.get('cfTgPollOffset') || 0;
const WELCOME = '안녕하세요! CronusFarm AI 봇입니다.\n\n질문: 농장 데이터(KMA·PHW·CCTV·MQTT) 참고 답변\n날씨: 날씨 / 기상 / 예보\n사진: 작물·해충·방제 AI 분석\n안내: /start';

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
const out4 = [];

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
  const text = String(m.text || m.caption || '').trim();
  const low = text.toLowerCase();
  const photos = m.photo;

  if (text === '/start' || text === '/help' || low === '시작' || low === '도움' || low === 'help') {
    out1.push(mkSend(cid, WELCOME));
    continue;
  }
  if (photos && photos.length && visionOn) {
    const best = photos[photos.length - 1];
    const busy = global.get('cfTgVisionBusy') || 0;
    if (busy && (Date.now() - busy) < 120000) {
      out1.push(mkSend(cid, '⏳ 이전 사진 분석이 진행 중입니다. 잠시 후 다시 보내 주세요.'));
      continue;
    }
    out4.push({
      chat_id: Number(cid),
      file_id: String(best.file_id || ''),
      ask_text: text
    });
    continue;
  }
  if (photos && photos.length && !visionOn) {
    out1.push(mkSend(cid, '사진 AI 비활성(CRONUSFARM_VISION_ENABLED=0). /start'));
    continue;
  }
  if (text.length === 0) {
    out1.push(mkSend(cid, '텍스트 질문 또는 작물·해충 사진을 보내 주세요. /start'));
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
return [out1, out2, out3, out4];"""

FN_PHOTO_RUN = r"""const cp = global.get('child_process');
if (!cp) {
  node.error('child_process 없음 — pi-nodered-patch-child-process-context.sh');
  return null;
}
const script = (env.get('CRONUSFARM_VISION_SCRIPT') || '/home/dooly/CronusFarm/scripts/cronusfarm_telegram_vision.py').toString().trim();
const fileId = (msg.file_id || '').toString().trim();
const chatId = Number(msg.chat_id);
const askText = (msg.ask_text || '').toString().trim();
if (!fileId || !chatId) { return null; }

global.set('cfTgVisionBusy', Date.now());
const token = (env.get('CRONUSFARM_TELEGRAM_BOT_TOKEN') || '').toString().trim();
if (token) {
  const ack = JSON.stringify({ chat_id: chatId, text: '📷 사진 분석 중… (작물·해충·방제, 30~90초)' });
  const ackUrl = 'https://api.telegram.org/bot' + token + '/sendMessage';
  const ackCmd = 'curl -s -m 15 -X POST -H ' + JSON.stringify('Content-Type: application/json; charset=utf-8')
    + ' -d ' + JSON.stringify(ack) + ' ' + JSON.stringify(ackUrl);
  try { cp.execSync(ackCmd, { encoding: 'utf8', maxBuffer: 1024 * 1024 }); } catch (e) { /* ignore */ }
}

let cmd = 'python3 ' + JSON.stringify(script)
  + ' --file-id ' + JSON.stringify(fileId)
  + ' --chat-id ' + String(chatId)
  + ' --send';
if (askText) {
  cmd += ' --question ' + JSON.stringify(askText);
}
try {
  const out = cp.execSync(cmd, { encoding: 'utf8', maxBuffer: 8 * 1024 * 1024, timeout: 180000 });
  node.log('vision ok: ' + (out || '').toString().slice(0, 120));
} catch (e) {
  let err = String(e.stderr || e.message || e).slice(0, 500);
  if (/429|RESOURCE_EXHAUSTED|rate limit/i.test(err)) {
    err = 'Gemini API 할당량 초과(429). 1~2분 후 재시도 또는 AI Studio 할당량 확인.';
  }
  node.error('vision 실패: ' + err);
  if (token) {
    const fail = JSON.stringify({ chat_id: chatId, text: '사진 AI 실패: ' + err + '\n\nPi: /etc/cronusfarm/nodered-telegram.env (GEMINI 키·모델)' });
    const failUrl = 'https://api.telegram.org/bot' + token + '/sendMessage';
    const failCmd = 'curl -s -m 15 -X POST -H ' + JSON.stringify('Content-Type: application/json; charset=utf-8')
      + ' -d ' + JSON.stringify(fail) + ' ' + JSON.stringify(failUrl);
    try { cp.execSync(failCmd, { encoding: 'utf8', maxBuffer: 1024 * 1024 }); } catch (e2) { /* ignore */ }
  }
} finally {
  global.set('cfTgVisionBusy', 0);
}
return null;"""


def patch_flow(path: Path) -> None:
    if not path.is_file():
        return
    flows = json.loads(path.read_text(encoding="utf-8-sig"))
    ids = {n.get("id") for n in flows if isinstance(n, dict)}

    send_wire = ["cf_fn_tg_curl_send"]
    for n in flows:
        if not isinstance(n, dict):
            continue
        if n.get("id") == "cf_hreq_tg_sendmsg":
            send_wire = ["cf_hreq_tg_sendmsg"]
            break

    for n in flows:
        if not isinstance(n, dict):
            continue
        if n.get("id") == "cf_fn_tg_dispatch":
            n["func"] = FN_DISPATCH
            n["outputs"] = 4
            n["wires"] = [
                send_wire,
                ["cf_fn_tg_weather_url"],
                ["cf_fn_tg_ollama_build"],
                ["cf_fn_tg_photo_run"],
            ]

    def upsert(node: dict) -> None:
        nid = node["id"]
        for i, n in enumerate(flows):
            if isinstance(n, dict) and n.get("id") == nid:
                flows[i] = {**n, **node}
                return
        flows.append(node)
        ids.add(nid)

    upsert(
        {
            "id": "cf_fn_tg_photo_run",
            "type": "function",
            "z": TAB,
            "name": "사진 AI (vision.py)",
            "func": FN_PHOTO_RUN,
            "outputs": 1,
            "timeout": 200,
            "noerr": 0,
            "initialize": "",
            "finalize": "",
            "libs": [],
            "x": 960,
            "y": 1080,
            "wires": [[]],
        }
    )

    path.write_text(json.dumps(flows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("OK", path.name)


def main() -> None:
    for name in (
        "flows_cronusfarm_mqtt.json",
        "flows_cronusfarm_dashboard.json",
        "CronusFarm_NodeRED_flow.json",
    ):
        patch_flow(ROOT / "nodered" / name)


if __name__ == "__main__":
    main()
