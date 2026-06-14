# -*- coding: utf-8 -*-
"""개발현황(ui_grp_devflow) — 통신 흐름도 4개를 별도 ui_template(높이 분리)로 배치."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEVFLOW = ROOT / "nodered" / "flows_cronusfarm_devflow_flow.json"
TARGET_GROUP = "ui_grp_devflow"
DATE_TAG = datetime.now().strftime("%Y%m%d")

STYLE = r"""
<style>
.cf-dev-arch{font-family:system-ui,'Malgun Gothic',sans-serif;color:#e8f0fe;max-width:1100px;margin:0 auto;padding:2px 0}
.cf-dev-arch .tag{display:inline-block;margin:0 0 8px;padding:4px 10px;border-radius:6px;background:#263238;border:1px solid #aed581;color:#aed581;font-size:12px;font-weight:800;letter-spacing:.04em}
.cf-dev-arch h3{margin:0 0 6px;font-size:1rem;color:#81d4fa;font-weight:700}
.cf-dev-arch .sub{font-size:11px;color:#9db0cc;margin:0 0 8px;line-height:1.45}
.cf-dev-arch svg{width:100%;height:auto;display:block}
</style>
"""

def _wrap(tag: str, title: str, sub: str, svg: str) -> str:
    return (
        f'<div class="cf-dev-arch"><span class="tag">{tag}</span>'
        f"<h3>{title}</h3><p class=\"sub\">{sub}</p>{svg}</div>"
    )


SVG_A = r"""<svg viewBox="0 0 920 280" xmlns="http://www.w3.org/2000/svg">
  <defs><marker id="a1" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#66bb6a"/></marker></defs>
  <rect x="30" y="100" width="100" height="44" rx="8" fill="#1b5e20" stroke="#66bb6a"/><text x="80" y="126" text-anchor="middle" fill="#e8f5e9" font-size="10" font-weight="700">R4</text>
  <rect x="30" y="170" width="100" height="40" rx="8" fill="#33691e" stroke="#aed581"/><text x="80" y="194" text-anchor="middle" fill="#f1f8e9" font-size="9">USB ttyACM</text>
  <line x1="80" y1="144" x2="80" y2="168" stroke="#aed581" stroke-width="2" marker-end="url(#a1)"/>
  <rect x="160" y="170" width="120" height="40" rx="8" fill="#004d40" stroke="#4db6ac"/><text x="220" y="194" text-anchor="middle" fill="#e0f2f1" font-size="9">r4-serial :18767</text>
  <rect x="310" y="155" width="140" height="55" rx="8" fill="#1a237e" stroke="#7986cb"/><text x="380" y="178" text-anchor="middle" fill="#e8eaf6" font-size="10" font-weight="700">sqlite_bridge</text><text x="380" y="196" text-anchor="middle" fill="#c5cae9" font-size="8">:18766</text>
  <rect x="490" y="40" width="110" height="40" rx="8" fill="#263238" stroke="#90a4ae"/><text x="545" y="64" text-anchor="middle" fill="#eceff1" font-size="9">Node-RED</text>
  <rect x="490" y="100" width="110" height="40" rx="8" fill="#0d47a1" stroke="#42a5f5"/><text x="545" y="124" text-anchor="middle" fill="#e3f2fd" font-size="9">Mosquitto</text>
  <rect x="640" y="40" width="90" height="40" rx="8" fill="#4a148c" stroke="#ba68c8"/><text x="685" y="64" text-anchor="middle" fill="#f3e5f5" font-size="9">farm-ui</text>
  <rect x="640" y="155" width="90" height="40" rx="8" fill="#1b4332" stroke="#2dff7a"/><text x="685" y="178" text-anchor="middle" fill="#d8ffe8" font-size="9">/ui</text>
  <line x1="280" y1="190" x2="308" y2="182" stroke="#4db6ac" stroke-width="2" marker-end="url(#a1)"/>
  <line x1="450" y1="180" x2="488" y2="60" stroke="#7986cb" stroke-width="2" marker-end="url(#a1)"/>
  <line x1="450" y1="188" x2="638" y2="60" stroke="#7986cb" stroke-width="1.5" stroke-dasharray="4 3" marker-end="url(#a1)"/>
  <line x1="450" y1="195" x2="638" y2="175" stroke="#2dff7a" stroke-width="2" marker-end="url(#a1)"/>
</svg>"""

SVG_B = r"""<svg viewBox="0 0 920 180" xmlns="http://www.w3.org/2000/svg">
  <defs><marker id="b1" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#ef5350"/></marker></defs>
  <rect x="40" y="60" width="90" height="44" rx="8" fill="#1b5e20" stroke="#66bb6a"/><text x="85" y="86" text-anchor="middle" fill="#e8f5e9" font-size="10">R4</text>
  <rect x="190" y="60" width="100" height="44" rx="8" fill="#b71c1c" stroke="#ef5350"/><text x="240" y="82" text-anchor="middle" fill="#ffcdd2" font-size="9">MQTT ✕</text>
  <rect x="330" y="60" width="100" height="44" rx="8" fill="#0d47a1" stroke="#42a5f5"/><text x="380" y="86" text-anchor="middle" fill="#e3f2fd" font-size="9">Mosquitto</text>
  <rect x="470" y="40" width="110" height="44" rx="8" fill="#263238" stroke="#90a4ae"/><text x="525" y="66" text-anchor="middle" fill="#ffcdd2" font-size="9">NR tele 없음</text>
  <rect x="470" y="100" width="110" height="44" rx="8" fill="#4a148c" stroke="#ba68c8"/><text x="525" y="126" text-anchor="middle" fill="#ffcdd2" font-size="9">모니터 offline</text>
  <rect x="640" y="70" width="120" height="44" rx="8" fill="#1a237e" stroke="#7986cb"/><text x="700" y="96" text-anchor="middle" fill="#ffcdd2" font-size="9">bridge/UI offline</text>
  <line x1="130" y1="82" x2="188" y2="82" stroke="#ef5350" stroke-width="2" stroke-dasharray="6 4"/>
  <line x1="430" y1="82" x2="468" y2="62" stroke="#ef5350" stroke-width="2" marker-end="url(#b1)"/>
</svg>"""

SVG_C = r"""<svg viewBox="0 0 920 260" xmlns="http://www.w3.org/2000/svg">
  <defs><marker id="c1" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#42a5f5"/></marker></defs>
  <rect x="20" y="15" width="200" height="32" rx="6" fill="#1b4332" stroke="#2dff7a"/><text x="120" y="36" text-anchor="middle" fill="#d8ffe8" font-size="10" font-weight="700">현장 R4 ↔ I2C ↔ R3</text>
  <rect x="260" y="15" width="400" height="32" rx="6" fill="#0d2137" stroke="#4fc3f7"/><text x="460" y="36" text-anchor="middle" fill="#e3f2fd" font-size="10" font-weight="700">Pi serial·bridge·NR·Mosq</text>
  <rect x="700" y="15" width="180" height="32" rx="6" fill="#4a148c" stroke="#ba68c8"/><text x="790" y="36" text-anchor="middle" fill="#f3e5f5" font-size="10">/ui farm-ui</text>
  <rect x="280" y="75" width="90" height="40" rx="8" fill="#1b5e20" stroke="#66bb6a"/><text x="325" y="99" text-anchor="middle" fill="#e8f5e9" font-size="9">R4</text>
  <rect x="280" y="135" width="90" height="36" rx="8" fill="#33691e" stroke="#aed581"/><text x="325" y="157" text-anchor="middle" fill="#f1f8e9" font-size="8">USB</text>
  <rect x="400" y="125" width="100" height="46" rx="8" fill="#004d40" stroke="#4db6ac"/><text x="450" y="152" text-anchor="middle" fill="#e0f2f1" font-size="9">데몬</text>
  <rect x="530" y="115" width="120" height="56" rx="8" fill="#1a237e" stroke="#7986cb"/><text x="590" y="145" text-anchor="middle" fill="#e8eaf6" font-size="9">bridge</text>
  <rect x="680" y="85" width="90" height="40" rx="8" fill="#263238" stroke="#90a4ae"/><text x="725" y="109" text-anchor="middle" fill="#eceff1" font-size="9">NR</text>
  <rect x="680" y="145" width="90" height="40" rx="8" fill="#0d47a1" stroke="#42a5f5"/><text x="725" y="169" text-anchor="middle" fill="#e3f2fd" font-size="8">Mosq</text>
  <line x1="325" y1="115" x2="325" y2="133" stroke="#aed581" stroke-width="2" marker-end="url(#c1)"/>
  <line x1="370" y1="153" x2="398" y2="147" stroke="#4db6ac" stroke-width="2" marker-end="url(#c1)"/>
  <line x1="500" y1="143" x2="678" y2="105" stroke="#7986cb" stroke-width="2" marker-end="url(#c1)"/>
  <line x1="650" y1="143" x2="788" y2="47" stroke="#2dff7a" stroke-width="2" marker-end="url(#c1)"/>
</svg>"""

SVG_D = r"""<svg viewBox="0 0 920 200" xmlns="http://www.w3.org/2000/svg">
  <defs><marker id="d1" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#ff7043"/></marker></defs>
  <rect x="50" y="35" width="80" height="40" rx="8" fill="#1b5e20" stroke="#66bb6a"/><text x="90" y="59" text-anchor="middle" fill="#e8f5e9" font-size="9">R4</text>
  <text x="155" y="59" fill="#ef5350" font-size="11" font-weight="700">MQTT ✕</text>
  <rect x="200" y="35" width="90" height="40" rx="8" fill="#0d47a1" stroke="#42a5f5"/><text x="245" y="59" text-anchor="middle" fill="#e3f2fd" font-size="9">Mosquitto</text>
  <rect x="330" y="25" width="100" height="36" rx="8" fill="#263238" stroke="#ef5350"/><text x="380" y="47" text-anchor="middle" fill="#ffcdd2" font-size="8">NR MQTT탭</text>
  <rect x="330" y="75" width="100" height="36" rx="8" fill="#4a148c" stroke="#ef5350"/><text x="380" y="97" text-anchor="middle" fill="#ffcdd2" font-size="8">connLineOk✕</text>
  <rect x="480" y="50" width="130" height="50" rx="8" fill="#1a237e" stroke="#7986cb"/><text x="545" y="72" text-anchor="middle" fill="#e8eaf6" font-size="9">sqlite_bridge</text><text x="545" y="88" text-anchor="middle" fill="#81c784" font-size="8">USB ingest OK</text>
  <rect x="50" y="120" width="80" height="36" rx="8" fill="#33691e" stroke="#aed581"/><text x="90" y="142" text-anchor="middle" fill="#f1f8e9" font-size="8">USB tele</text>
  <line x1="130" y1="138" x2="478" y2="75" stroke="#66bb6a" stroke-width="2" marker-end="url(#d1)"/>
  <text x="640" y="55" fill="#9db0cc" font-size="9">mqtt_status_log offline ≠ farm 중단</text>
  <text x="640" y="75" fill="#81c784" font-size="9">tele_sample 1Hz = USB primary 정상</text>
</svg>"""

TPL_SPECS = (
    (
        f"ui_tpl_cf_comm_{DATE_TAG}_01",
        f"통신흐름_하이브리드목표_{DATE_TAG}_01",
        0,
        9,
        STYLE
        + _wrap(
            f"통신흐름_하이브리드목표_{DATE_TAG}_01",
            "A. 목표 하이브리드 (USB primary + Mosquitto 유지)",
            "R4 farm tele/cmd → USB → bridge. Mosquitto는 KMA·NR 유지.",
            SVG_A,
        ),
    ),
    (
        f"ui_tpl_cf_comm_{DATE_TAG}_02",
        f"통신흐름_MQTT미전환_{DATE_TAG}_02",
        1,
        7,
        STYLE
        + _wrap(
            f"통신흐름_MQTT미전환_{DATE_TAG}_02",
            "B. MQTT offline · USB 미적용",
            "구성 미전환 시 R4↔Pi farm 경로 끊김.",
            SVG_B,
        ),
    ),
    (
        f"ui_tpl_cf_comm_{DATE_TAG}_03",
        f"통신흐름_하이브리드Pi_{DATE_TAG}_03",
        2,
        9,
        STYLE
        + _wrap(
            f"통신흐름_하이브리드Pi_{DATE_TAG}_03",
            "C. 하이브리드 목표 (Pi·현장·/ui)",
            "현장=R4·R3 · Pi=USB·bridge·NR · farm-ui=/ui",
            SVG_C,
        ),
    ),
    (
        f"ui_tpl_cf_comm_{DATE_TAG}_04",
        f"통신흐름_USB복구상태_{DATE_TAG}_04",
        3,
        8,
        STYLE
        + _wrap(
            f"통신흐름_USB복구상태_{DATE_TAG}_04",
            "D. MQTT offline + USB primary 적용 후",
            "MQTT 로그 offline이어도 tele 1Hz면 farm 정상.",
            SVG_D,
        ),
    ),
)

REMOVE_IDS = frozenset(
    {
        "ui_tpl_devflow_comm_diagrams",
        "ui_tpl_devflow_hybrid_flow",
        "ui_tpl_devflow_dev_status",
        "ui_tpl_devflow_mqtt_root",
        "ui_tpl_devflow_offline_chk",
    }
)


def main() -> int:
    if not DEVFLOW.is_file():
        print(f"없음: {DEVFLOW}", file=sys.stderr)
        return 1
    raw: list = json.loads(DEVFLOW.read_text(encoding="utf-8-sig"))
    by_id: dict[str, dict] = {n["id"]: n for n in raw if isinstance(n, dict) and n.get("id")}

    for rid in REMOVE_IDS:
        by_id.pop(rid, None)
    for n in list(by_id.values()):
        if n.get("type") == "ui_template" and n.get("group") == TARGET_GROUP:
            tid = str(n.get("id") or "")
            if tid.startswith("ui_tpl_cf_comm_") and DATE_TAG not in tid:
                by_id.pop(tid, None)

    for tid, name, order, height, fmt in TPL_SPECS:
        node = by_id.get(tid)
        if not isinstance(node, dict):
            node = {
                "id": tid,
                "type": "ui_template",
                "z": "tab_cronus_devflow",
                "group": TARGET_GROUP,
                "name": name,
                "width": "12",
                "storeOutMessages": True,
                "fwdInMessages": True,
                "resendOnRefresh": True,
                "templateScope": "local",
                "className": "",
                "x": 400,
                "y": 40 + order * 55,
                "wires": [[]],
            }
            by_id[tid] = node
        node["format"] = fmt
        node["order"] = order
        node["height"] = height
        node["group"] = TARGET_GROUP
        node["name"] = name

    for n in by_id.values():
        if n.get("type") != "ui_template" or n.get("group") != TARGET_GROUP:
            continue
        tid = n.get("id")
        if any(tid == spec[0] for spec in TPL_SPECS):
            continue
        o = int(n.get("order") or 99)
        if o < 20:
            n["order"] = o + 10

    DEVFLOW.write_text(json.dumps(list(by_id.values()), ensure_ascii=False), encoding="utf-8")
    print(f"OK {DEVFLOW.name} 4 widgets {DATE_TAG} → {TARGET_GROUP}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
