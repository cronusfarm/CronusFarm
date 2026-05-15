# -*- coding: utf-8 -*-
"""개발환경 탭: 모니터 데이터 출처·제어 흐름 다이어그램 ui_template 추가."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEVFLOW = ROOT / "nodered" / "flows_cronusfarm_devflow_flow.json"

MONITOR_DATA_SRC = r"""<div class="cf-dev-arch">
<style>
.cf-dev-arch{font-family:system-ui,'Malgun Gothic',sans-serif;color:#e8f0fe;max-width:1100px;margin:0 auto;padding:4px 0}
.cf-dev-arch h3{margin:0 0 8px;font-size:1rem;color:#aed581;font-weight:800}
.cf-dev-arch .sub{font-size:11px;color:#9db0cc;margin:0 0 10px;line-height:1.45}
.cf-dev-arch svg{width:100%;height:auto;display:block}
</style>
<h3>데이터 출처 (모니터)</h3>
<p class="sub">모니터 화면에 보이는 값의 “진실” 경로 — UI 토글만으로는 DB/그래프가 바뀌지 않음</p>
<svg viewBox="0 0 920 200" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="모니터 데이터 출처">
  <defs>
    <marker id="arr-g" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#7cb342"/></marker>
  </defs>
  <rect x="8" y="70" width="100" height="44" rx="8" fill="#1b5e20" stroke="#66bb6a" stroke-width="1.5"/>
  <text x="58" y="97" text-anchor="middle" fill="#e8f5e9" font-size="11" font-weight="700">Arduino</text>
  <rect x="140" y="70" width="90" height="44" rx="8" fill="#0d47a1" stroke="#42a5f5"/>
  <text x="185" y="97" text-anchor="middle" fill="#e3f2fd" font-size="11" font-weight="700">MQTT tele</text>
  <rect x="262" y="50" width="110" height="44" rx="8" fill="#263238" stroke="#90a4ae"/>
  <text x="317" y="77" text-anchor="middle" fill="#eceff1" font-size="10" font-weight="700">NR tele 파싱</text>
  <rect x="262" y="108" width="110" height="44" rx="8" fill="#1a237e" stroke="#7986cb"/>
  <text x="317" y="128" text-anchor="middle" fill="#e8eaf6" font-size="10" font-weight="700">tele_channel_fact</text>
  <rect x="400" y="108" width="120" height="44" rx="8" fill="#1a237e" stroke="#7986cb"/>
  <text x="460" y="128" text-anchor="middle" fill="#e8eaf6" font-size="10" font-weight="700">Bed 24h 타임라인</text>
  <rect x="8" y="8" width="100" height="44" rx="8" fill="#4a148c" stroke="#ba68c8"/>
  <text x="58" y="28" text-anchor="middle" fill="#f3e5f5" font-size="10" font-weight="700">Tuya PHW3988</text>
  <rect x="140" y="8" width="90" height="44" rx="8" fill="#263238" stroke="#ffb74d"/>
  <text x="185" y="28" text-anchor="middle" fill="#fff3e0" font-size="10" font-weight="700">fn_map</text>
  <rect x="262" y="8" width="110" height="44" rx="8" fill="#1a237e" stroke="#7986cb"/>
  <text x="317" y="28" text-anchor="middle" fill="#e8eaf6" font-size="10" font-weight="700">sensor_reading</text>
  <rect x="400" y="8" width="120" height="44" rx="8" fill="#1a237e" stroke="#7986cb"/>
  <text x="460" y="28" text-anchor="middle" fill="#e8eaf6" font-size="10" font-weight="700">게이지·24h 수질</text>
  <line x1="108" y1="92" x2="138" y2="92" stroke="#66bb6a" stroke-width="2" marker-end="url(#arr-g)"/>
  <line x1="230" y1="92" x2="260" y2="72" stroke="#90a4ae" stroke-width="2" marker-end="url(#arr-g)"/>
  <line x1="372" y1="72" x2="398" y2="130" stroke="#7986cb" stroke-width="2" marker-end="url(#arr-g)"/>
  <line x1="108" y1="30" x2="138" y2="30" stroke="#ba68c8" stroke-width="2" marker-end="url(#arr-g)"/>
  <line x1="230" y1="30" x2="260" y2="30" stroke="#ffb74d" stroke-width="2" marker-end="url(#arr-g)"/>
  <line x1="372" y1="30" x2="398" y2="30" stroke="#7986cb" stroke-width="2" marker-end="url(#arr-g)"/>
  <text x="540" y="40" fill="#81c784" font-size="10">수동/스케줄 → tele·cmd 경유 후 DB 적재</text>
  <text x="540" y="130" fill="#90caf9" font-size="10">GET /api/channel/timeline</text>
  <text x="540" y="58" fill="#ffcc80" font-size="10">POST /ingest/sensor · GET /api/sensor/series</text>
</svg>
</div>"""

CONTROL_FLOW = r"""<div class="cf-dev-arch">
<style>
.cf-dev-arch{font-family:system-ui,'Malgun Gothic',sans-serif;color:#e8f0fe;max-width:1100px;margin:0 auto;padding:8px 0 4px}
.cf-dev-arch h3{margin:0 0 8px;font-size:1rem;color:#aed581;font-weight:800}
.cf-dev-arch .sub{font-size:11px;color:#9db0cc;margin:0 0 10px;line-height:1.45}
.cf-dev-arch svg{width:100%;height:auto;display:block}
</style>
<h3>목표 데이터·제어 흐름</h3>
<p class="sub">설정·모니터 UI는 표현만 — cmd/tele·DB는 MQTT 탭·bridge 단일 경로</p>
<svg viewBox="0 0 920 340" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="제어 흐름">
  <defs>
    <marker id="arr-b" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#42a5f5"/></marker>
  </defs>
  <rect x="320" y="8" width="280" height="52" rx="10" fill="#0d2137" stroke="#4fc3f7" stroke-width="2"/>
  <text x="460" y="32" text-anchor="middle" fill="#e3f2fd" font-size="12" font-weight="800">/ui Dashboard 1</text>
  <text x="460" y="48" text-anchor="middle" fill="#90caf9" font-size="10">모니터 · 설정(iframe) · 개발환경</text>
  <rect x="40" y="88" width="200" height="48" rx="8" fill="#1b4332" stroke="#2dff7a"/>
  <text x="140" y="110" text-anchor="middle" fill="#d8ffe8" font-size="11" font-weight="700">CronusFarm-모니터</text>
  <text x="140" y="126" text-anchor="middle" fill="#9ccc65" font-size="9">타일·타임라인·PHW·AI</text>
  <rect x="360" y="88" width="200" height="48" rx="8" fill="#4a148c" stroke="#ce93d8"/>
  <text x="460" y="110" text-anchor="middle" fill="#f3e5f5" font-size="11" font-weight="700">CronusFarm-설정</text>
  <text x="460" y="126" text-anchor="middle" fill="#e1bee7" font-size="9">Bed/스케줄·API iframe</text>
  <rect x="320" y="160" width="280" height="56" rx="10" fill="#263238" stroke="#ffb74d" stroke-width="2"/>
  <text x="460" y="184" text-anchor="middle" fill="#fff3e0" font-size="11" font-weight="800">Node-RED (MQTT 탭)</text>
  <text x="460" y="200" text-anchor="middle" fill="#ffcc80" font-size="9">공통 cmd · tele 파싱 · http→bridge</text>
  <rect x="320" y="240" width="130" height="48" rx="8" fill="#1a237e" stroke="#7986cb"/>
  <text x="385" y="262" text-anchor="middle" fill="#e8eaf6" font-size="10" font-weight="700">SQLite bridge</text>
  <text x="385" y="276" text-anchor="middle" fill="#c5cae9" font-size="9">:18766</text>
  <rect x="470" y="240" width="130" height="48" rx="8" fill="#0d47a1" stroke="#42a5f5"/>
  <text x="535" y="262" text-anchor="middle" fill="#e3f2fd" font-size="10" font-weight="700">Mosquitto</text>
  <rect x="620" y="240" width="120" height="48" rx="8" fill="#1b5e20" stroke="#66bb6a"/>
  <text x="680" y="262" text-anchor="middle" fill="#e8f5e9" font-size="10" font-weight="700">Arduino R4</text>
  <line x1="460" y1="60" x2="460" y2="86" stroke="#4fc3f7" stroke-width="2"/>
  <line x1="140" y1="136" x2="140" y2="158" stroke="#2dff7a" stroke-width="2" marker-end="url(#arr-b)"/>
  <line x1="460" y1="136" x2="460" y2="158" stroke="#ce93d8" stroke-width="2" marker-end="url(#arr-b)"/>
  <line x1="400" y1="188" x2="385" y2="238" stroke="#7986cb" stroke-width="2" marker-end="url(#arr-b)"/>
  <line x1="520" y1="188" x2="535" y2="238" stroke="#42a5f5" stroke-width="2" marker-end="url(#arr-b)"/>
  <line x1="600" y1="264" x2="618" y2="264" stroke="#66bb6a" stroke-width="2" marker-end="url(#arr-b)"/>
  <line x1="680" y1="240" x2="520" y2="200" stroke="#66bb6a" stroke-width="1.5" stroke-dasharray="4 3" marker-end="url(#arr-b)"/>
  <text x="720" y="210" fill="#81c784" font-size="9">tele 1Hz</text>
  <text x="40" y="310" fill="#9db0cc" font-size="10">nginx /farm/* → NR:1882 → bridge · SCHED_JSON·채널 cmd → MQTT</text>
</svg>
</div>"""

TPL_SPECS = (
    ("ui_tpl_devflow_monitor_data_src", "개발환경: 데이터 출처(모니터)", 0, 7, MONITOR_DATA_SRC),
    ("ui_tpl_devflow_control_flow", "개발환경: 제어 흐름(목표)", 1, 9, CONTROL_FLOW),
)


def main() -> int:
    if not DEVFLOW.is_file():
        print(f"없음: {DEVFLOW}", file=sys.stderr)
        return 1
    raw: list = json.loads(DEVFLOW.read_text(encoding="utf-8-sig"))
    by_id: dict[str, dict] = {n["id"]: n for n in raw if isinstance(n, dict) and n.get("id")}

    grp = "ui_grp_devflow"
    for n in by_id.values():
        if n.get("type") == "ui_group" and n.get("tab") == "ui_tab_devflow":
            grp = n["id"]
            break

    for tid, name, order, height, fmt in TPL_SPECS:
        node = by_id.get(tid)
        if not isinstance(node, dict):
            node = {
                "id": tid,
                "type": "ui_template",
                "z": "tab_cronus_devflow",
                "group": grp,
                "name": name,
                "width": "12",
                "storeOutMessages": True,
                "fwdInMessages": True,
                "resendOnRefresh": True,
                "templateScope": "local",
                "className": "",
                "x": 400,
                "y": 80 + order * 40,
                "wires": [[]],
            }
            by_id[tid] = node
        node["format"] = fmt
        node["order"] = order
        node["height"] = height
        node["group"] = grp

    # 기존 템플릿 order 밀기 (nodered_paths 제외 상단 2칸)
    bump = {tid: ord_ for tid, _, ord_, _, _ in TPL_SPECS}
    for n in by_id.values():
        if n.get("type") != "ui_template" or n.get("group") != grp:
            continue
        tid = n.get("id")
        if tid in bump:
            continue
        o = int(n.get("order") or 99)
        if o < 90:
            n["order"] = o + 2

    DEVFLOW.write_text(json.dumps(list(by_id.values()), ensure_ascii=False), encoding="utf-8")
    print(f"OK {DEVFLOW.name} arch diagrams (monitor data + control flow)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
