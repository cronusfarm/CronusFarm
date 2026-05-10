# -*- coding: utf-8 -*-
"""CronusFarm 텔레그램 뉴스 파이프라인 패치.

적용 내용:
1) KMA snapshot MQTT 수신 시 flow/global context 캐시 노드 추가
2) 일일 뉴스 함수(cf_fn_tg_news_daily)를 실데이터 기반 템플릿으로 교체
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
TAB_NEWS = "b1c5a1f1d7a2a3a1"
TAB_DASH = "tab_cronus_dash"

FN_KMA_CACHE = """let p = msg.payload;
if (typeof p === 'string') {
  try { p = JSON.parse(p); } catch (e) { return msg; }
}
if (p && typeof p === 'object') {
  flow.set('kmaSnapshot', p);
  global.set('kmaSnapshot', p);
  flow.set('kmaSnapshotTs', Date.now());
  global.set('kmaSnapshotTs', Date.now());
}
msg.payload = p;
return msg;"""

FN_NEWS = """const token = (env.get('CRONUSFARM_TELEGRAM_BOT_TOKEN') || '').toString().trim();
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

const now = new Date(Date.now() + 9 * 60 * 60 * 1000);
const mon = String(now.getUTCMonth() + 1).padStart(2, '0');
const day = String(now.getUTCDate()).padStart(2, '0');

const teleTs = fmtKst(flow.get('arduinoLastTeleMs'));
const statusTs = fmtKst(flow.get('arduinoLastStatusMs'));
const gState = (flow.get('lastTeleG') || '').toString().trim() || '미수신';
const lastTele = (flow.get('lastTeleStr') || '').toString().trim();
const telePreview = lastTele ? lastTele.slice(0, 120) : '미수신';

const kma = flow.get('kmaSnapshot') || global.get('kmaSnapshot') || {};
const kmaTs = flow.get('kmaSnapshotTs') || global.get('kmaSnapshotTs') || null;
const temp = (kma.kma_temp ?? '미수신');
const hum = (kma.kma_humidity ?? '미수신');
const ptyRaw = (kma.kma_precip_type ?? '');
const pcp = (kma.kma_precip_1h ?? '미수신');
const ptyMap = { '0': '없음', '1': '비', '2': '비/눈', '3': '눈', '4': '소나기' };
const pty = (ptyRaw === '' || ptyRaw == null) ? '미수신' : (ptyMap[String(ptyRaw)] || String(ptyRaw));

const text =
`🌙 ${mon}월 ${day}일 저녁 영농 준비

🌤️ 날씨: 🌡️ 현재 기온: ${temp}${temp === '미수신' ? '' : '°C'}  |  💧 습도: ${hum}${hum === '미수신' ? '' : '%'}  |  🌧️ 강수형태: ${pty}  |  ☔ 1시간 강수: ${pcp}${pcp === '미수신' ? '' : 'mm'}
🛰️ 날씨 기준시각: ${fmtKst(kmaTs)}

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


def main() -> None:
    flows = json.loads(FLOW.read_text(encoding="utf-8"))
    ids = {n.get("id") for n in flows if isinstance(n, dict)}

    # 1) KMA 캐시 노드 추가 및 wire 연결
    if "cf_fn_kma_cache" not in ids:
        flows.append(
            {
                "id": "cf_fn_kma_cache",
                "type": "function",
                "z": TAB_DASH,
                "name": "KMA snapshot cache",
                "func": FN_KMA_CACHE,
                "outputs": 1,
                "timeout": 0,
                "noerr": 0,
                "initialize": "",
                "finalize": "",
                "libs": [],
                "x": 490,
                "y": 1000,
                "wires": [["ui_tpl_farm_env"]],
            }
        )

    for node in flows:
        if not isinstance(node, dict):
            continue
        if node.get("id") == "mqtt_in_kma_snap":
            wires = node.get("wires", [[]])
            if not wires:
                wires = [[]]
            first = wires[0]
            if "cf_fn_kma_cache" not in first:
                first = ["cf_fn_kma_cache"]
            node["wires"] = [first]
        if node.get("id") == "cf_fn_kma_cache":
            node["z"] = TAB_DASH
            node["func"] = FN_KMA_CACHE
            node["wires"] = [["ui_tpl_farm_env"]]

        # 2) 뉴스 함수 업데이트
        if node.get("id") == "cf_fn_tg_news_daily":
            node["z"] = TAB_NEWS
            node["func"] = FN_NEWS

    FLOW.write_text(json.dumps(flows, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    print("OK patched telegram news pipeline:", FLOW)


if __name__ == "__main__":
    main()
