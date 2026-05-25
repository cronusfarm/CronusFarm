# -*- coding: utf-8 -*-
"""개발현황(ui_grp_devflow /ui 탭 CronusFarm 개발현황) — 통신 흐름도 4장 일괄."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEVFLOW = ROOT / "nodered" / "flows_cronusfarm_devflow_flow.json"
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

# ui_grp_devflow = dashboard 의 "CronusFarm 개발현황" 탭 본문
TARGET_GROUP = "ui_grp_devflow"
TPL_ID = "ui_tpl_devflow_comm_diagrams"
REMOVE_IDS = frozenset(
    {
        "ui_tpl_devflow_hybrid_flow",
        "ui_tpl_devflow_dev_status",
        "ui_tpl_devflow_mqtt_root",
        "ui_tpl_devflow_offline_chk",
    }
)

ALL_FOUR = r"""<div class="cf-dev-arch cf-dev-scroll">
<style>
.cf-dev-arch{font-family:system-ui,'Malgun Gothic',sans-serif;color:#e8f0fe;max-width:1100px;margin:0 auto;padding:4px 0}
.cf-dev-scroll{max-height:min(92vh,5200px);overflow-y:auto;overflow-x:hidden;-webkit-overflow-scrolling:touch}
.cf-dev-arch h3{margin:18px 0 6px;font-size:1.02rem;color:#aed581;font-weight:800}
.cf-dev-arch h3:first-child{margin-top:0}
.cf-dev-arch .sub{font-size:11px;color:#9db0cc;margin:0 0 8px;line-height:1.45}
.cf-dev-arch svg{width:100%;height:auto;display:block;margin:0 0 6px}
</style>

<h3>A. 목표 하이브리드 (USB primary + Mosquitto 유지)</h3>
<p class="sub">R4 farm tele/cmd는 USB→데몬→bridge. Mosquitto는 KMA·NR 등 유지.</p>
<svg viewBox="0 0 920 300" xmlns="http://www.w3.org/2000/svg">
  <defs><marker id="a1" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#66bb6a"/></marker></defs>
  <rect x="30" y="110" width="100" height="44" rx="8" fill="#1b5e20" stroke="#66bb6a"/><text x="80" y="136" text-anchor="middle" fill="#e8f5e9" font-size="10" font-weight="700">R4</text>
  <rect x="30" y="180" width="100" height="40" rx="8" fill="#33691e" stroke="#aed581"/><text x="80" y="204" text-anchor="middle" fill="#f1f8e9" font-size="9">USB ttyACM</text>
  <line x1="80" y1="154" x2="80" y2="178" stroke="#aed581" stroke-width="2" marker-end="url(#a1)"/>
  <rect x="160" y="180" width="120" height="40" rx="8" fill="#004d40" stroke="#4db6ac"/><text x="220" y="204" text-anchor="middle" fill="#e0f2f1" font-size="9">r4-serial :18767</text>
  <rect x="310" y="165" width="140" height="55" rx="8" fill="#1a237e" stroke="#7986cb"/><text x="380" y="188" text-anchor="middle" fill="#e8eaf6" font-size="10" font-weight="700">sqlite_bridge</text><text x="380" y="204" text-anchor="middle" fill="#c5cae9" font-size="8">:18766 ingest/api</text>
  <rect x="490" y="50" width="110" height="40" rx="8" fill="#263238" stroke="#90a4ae"/><text x="545" y="74" text-anchor="middle" fill="#eceff1" font-size="9">Node-RED</text>
  <rect x="490" y="110" width="110" height="40" rx="8" fill="#0d47a1" stroke="#42a5f5"/><text x="545" y="134" text-anchor="middle" fill="#e3f2fd" font-size="9">Mosquitto</text>
  <rect x="640" y="50" width="90" height="40" rx="8" fill="#4a148c" stroke="#ba68c8"/><text x="685" y="74" text-anchor="middle" fill="#f3e5f5" font-size="9">farm-ui</text>
  <rect x="640" y="165" width="90" height="40" rx="8" fill="#1b4332" stroke="#2dff7a"/><text x="685" y="188" text-anchor="middle" fill="#d8ffe8" font-size="9">/ui</text>
  <line x1="280" y1="200" x2="308" y2="192" stroke="#4db6ac" stroke-width="2" marker-end="url(#a1)"/>
  <line x1="450" y1="190" x2="488" y2="70" stroke="#7986cb" stroke-width="2" marker-end="url(#a1)"/>
  <line x1="450" y1="195" x2="638" y2="70" stroke="#7986cb" stroke-width="1.5" stroke-dasharray="4 3" marker-end="url(#a1)"/>
  <line x1="450" y1="200" x2="638" y2="185" stroke="#2dff7a" stroke-width="2" marker-end="url(#a1)"/>
  <line x1="130" y1="130" x2="488" y2="128" stroke="#42a5f5" stroke-width="1.5" stroke-dasharray="5 4"/><text x="300" y="122" fill="#90caf9" font-size="8">롤백 MQTT</text>
</svg>

<h3>B. MQTT offline · USB 미적용 (전전 답변)</h3>
<p class="sub">구성 미전환 시 — R4↔Pi farm 경로 끊김.</p>
<svg viewBox="0 0 920 200" xmlns="http://www.w3.org/2000/svg">
  <defs><marker id="b1" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#ef5350"/></marker></defs>
  <rect x="40" y="70" width="90" height="44" rx="8" fill="#1b5e20" stroke="#66bb6a"/><text x="85" y="96" text-anchor="middle" fill="#e8f5e9" font-size="10">R4</text>
  <rect x="200" y="70" width="100" height="44" rx="8" fill="#b71c1c" stroke="#ef5350"/><text x="250" y="90" text-anchor="middle" fill="#ffcdd2" font-size="9">MQTT ✕</text>
  <rect x="340" y="70" width="100" height="44" rx="8" fill="#0d47a1" stroke="#42a5f5"/><text x="390" y="96" text-anchor="middle" fill="#e3f2fd" font-size="9">Mosquitto</text>
  <rect x="480" y="50" width="110" height="44" rx="8" fill="#263238" stroke="#90a4ae"/><text x="535" y="76" text-anchor="middle" fill="#ffcdd2" font-size="9">NR tele 없음</text>
  <rect x="480" y="110" width="110" height="44" rx="8" fill="#4a148c" stroke="#ba68c8"/><text x="535" y="136" text-anchor="middle" fill="#ffcdd2" font-size="9">모니터 offline</text>
  <rect x="650" y="80" width="120" height="44" rx="8" fill="#1a237e" stroke="#7986cb"/><text x="710" y="106" text-anchor="middle" fill="#ffcdd2" font-size="9">bridge/UI offline</text>
  <line x1="130" y1="92" x2="198" y2="92" stroke="#ef5350" stroke-width="2" stroke-dasharray="6 4"/>
  <line x1="300" y1="92" x2="338" y2="92" stroke="#90a4ae" stroke-width="1.5" marker-end="url(#b1)"/>
  <line x1="440" y1="92" x2="478" y2="72" stroke="#ef5350" stroke-width="2" marker-end="url(#b1)"/>
</svg>

<h3>C. 하이브리드 목표 (전 답변)</h3>
<p class="sub">현장=R4·R3 I2C · Pi=USB·bridge·NR·Mosquitto · farm-ui=/ui</p>
<svg viewBox="0 0 920 280" xmlns="http://www.w3.org/2000/svg">
  <defs><marker id="c1" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#42a5f5"/></marker></defs>
  <rect x="20" y="20" width="200" height="36" rx="6" fill="#1b4332" stroke="#2dff7a"/><text x="120" y="42" text-anchor="middle" fill="#d8ffe8" font-size="10" font-weight="700">현장: R4 ↔ I2C ↔ R3</text>
  <rect x="260" y="20" width="400" height="36" rx="6" fill="#0d2137" stroke="#4fc3f7"/><text x="460" y="42" text-anchor="middle" fill="#e3f2fd" font-size="10" font-weight="700">Pi: serial·bridge·NR·Mosquitto</text>
  <rect x="700" y="20" width="180" height="36" rx="6" fill="#4a148c" stroke="#ba68c8"/><text x="790" y="42" text-anchor="middle" fill="#f3e5f5" font-size="10">farm-ui /ui</text>
  <rect x="280" y="80" width="90" height="40" rx="8" fill="#1b5e20" stroke="#66bb6a"/><text x="325" y="104" text-anchor="middle" fill="#e8f5e9" font-size="9">R4</text>
  <rect x="280" y="140" width="90" height="36" rx="8" fill="#33691e" stroke="#aed581"/><text x="325" y="162" text-anchor="middle" fill="#f1f8e9" font-size="8">USB</text>
  <rect x="400" y="130" width="100" height="46" rx="8" fill="#004d40" stroke="#4db6ac"/><text x="450" y="152" text-anchor="middle" fill="#e0f2f1" font-size="9">데몬</text>
  <rect x="530" y="120" width="120" height="56" rx="8" fill="#1a237e" stroke="#7986cb"/><text x="590" y="148" text-anchor="middle" fill="#e8eaf6" font-size="9">bridge</text>
  <rect x="680" y="90" width="90" height="40" rx="8" fill="#263238" stroke="#90a4ae"/><text x="725" y="114" text-anchor="middle" fill="#eceff1" font-size="9">NR</text>
  <rect x="680" y="150" width="90" height="40" rx="8" fill="#0d47a1" stroke="#42a5f5"/><text x="725" y="174" text-anchor="middle" fill="#e3f2fd" font-size="8">Mosq</text>
  <line x1="325" y1="120" x2="325" y2="138" stroke="#aed581" stroke-width="2" marker-end="url(#c1)"/>
  <line x1="370" y1="158" x2="398" y2="152" stroke="#4db6ac" stroke-width="2" marker-end="url(#c1)"/>
  <line x1="500" y1="148" x2="678" y2="110" stroke="#7986cb" stroke-width="2" marker-end="url(#c1)"/>
  <line x1="500" y1="155" x2="678" y2="170" stroke="#42a5f5" stroke-width="1.5" stroke-dasharray="4 3" marker-end="url(#c1)"/>
  <line x1="650" y1="148" x2="788" y2="56" stroke="#2dff7a" stroke-width="2" marker-end="url(#c1)"/>
</svg>

<h3>D. MQTT offline + USB 미적용 (전 답변 · 현재 추정)</h3>
<p class="sub">USB primary 적용 후에는 A/C 경로로 tele·cmd 복구(지금 Pi tele 542B/1Hz OK).</p>
<svg viewBox="0 0 920 220" xmlns="http://www.w3.org/2000/svg">
  <defs><marker id="d1" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#ff7043"/></marker></defs>
  <rect x="50" y="40" width="80" height="40" rx="8" fill="#1b5e20" stroke="#66bb6a"/><text x="90" y="64" text-anchor="middle" fill="#e8f5e9" font-size="9">R4</text>
  <text x="150" y="64" fill="#ef5350" font-size="11" font-weight="700">MQTT ✕</text>
  <rect x="200" y="40" width="90" height="40" rx="8" fill="#0d47a1" stroke="#42a5f5"/><text x="245" y="64" text-anchor="middle" fill="#e3f2fd" font-size="9">Mosquitto</text>
  <rect x="330" y="30" width="100" height="36" rx="8" fill="#263238" stroke="#ef5350"/><text x="380" y="52" text-anchor="middle" fill="#ffcdd2" font-size="8">NR MQTT탭</text>
  <rect x="330" y="80" width="100" height="36" rx="8" fill="#4a148c" stroke="#ef5350"/><text x="380" y="102" text-anchor="middle" fill="#ffcdd2" font-size="8">connLineOk✕</text>
  <rect x="480" y="55" width="130" height="50" rx="8" fill="#1a237e" stroke="#7986cb"/><text x="545" y="78" text-anchor="middle" fill="#e8eaf6" font-size="9">sqlite_bridge</text><text x="545" y="94" text-anchor="middle" fill="#81c784" font-size="8">USB ingest OK</text>
  <rect x="50" y="130" width="80" height="36" rx="8" fill="#33691e" stroke="#aed581"/><text x="90" y="152" text-anchor="middle" fill="#f1f8e9" font-size="8">USB tele</text>
  <line x1="130" y1="148" x2="478" y2="80" stroke="#66bb6a" stroke-width="2" marker-end="url(#d1)"/>
  <line x1="130" y1="60" x2="198" y2="60" stroke="#ef5350" stroke-width="2" stroke-dasharray="6 4"/>
  <line x1="290" y1="60" x2="328" y2="48" stroke="#ef5350" stroke-width="1.5" marker-end="url(#d1)"/>
  <text x="650" y="70" fill="#9db0cc" font-size="9">mqtt_status_log offline = MQTT LWT·구독 없음</text>
  <text x="650" y="88" fill="#81c784" font-size="9">tele_sample 1Hz = USB primary 정상</text>
</svg>
</div>"""


def _patch_file(path: Path) -> None:
    raw: list = json.loads(path.read_text(encoding="utf-8-sig"))
    by_id: dict[str, dict] = {n["id"]: n for n in raw if isinstance(n, dict) and n.get("id")}

    for rid in REMOVE_IDS:
        by_id.pop(rid, None)

    node = by_id.get(TPL_ID)
    if not isinstance(node, dict):
        node = {
            "id": TPL_ID,
            "type": "ui_template",
            "z": "tab_cronus_devflow",
            "group": TARGET_GROUP,
            "name": "개발현황: 통신 흐름도 (4장)",
            "order": 0,
            "width": "12",
            "height": 28,
            "storeOutMessages": True,
            "fwdInMessages": True,
            "resendOnRefresh": True,
            "templateScope": "local",
            "className": "",
            "x": 400,
            "y": 40,
            "wires": [[]],
        }
        by_id[TPL_ID] = node
    node["format"] = ALL_FOUR
    node["group"] = TARGET_GROUP
    node["order"] = 0
    node["height"] = 28
    node["name"] = "개발현황: 통신 흐름도 (4장)"

    for n in by_id.values():
        if n.get("type") != "ui_template" or n.get("group") != TARGET_GROUP:
            continue
        if n.get("id") == TPL_ID:
            continue
        o = int(n.get("order") or 99)
        if o < 10:
            n["order"] = o + 1

    path.write_text(json.dumps(list(by_id.values()), ensure_ascii=False), encoding="utf-8")
    print(f"OK {path.name} → {TARGET_GROUP}")


def main() -> int:
    if not DEVFLOW.is_file():
        print(f"없음: {DEVFLOW}", file=sys.stderr)
        return 1
    _patch_file(DEVFLOW)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
