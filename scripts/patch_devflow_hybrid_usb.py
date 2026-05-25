# -*- coding: utf-8 -*-
"""개발환경(/ui) 탭: 하이브리드 USB·MQTT 통신 흐름·개발현황·MQTT 근본원인 패널."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEVFLOW = ROOT / "nodered" / "flows_cronusfarm_devflow_flow.json"

HYBRID_FLOW = r"""<div class="cf-dev-arch">
<style>
.cf-dev-arch{font-family:system-ui,'Malgun Gothic',sans-serif;color:#e8f0fe;max-width:1100px;margin:0 auto;padding:6px 0}
.cf-dev-arch h3{margin:0 0 6px;font-size:1.05rem;color:#aed581;font-weight:800}
.cf-dev-arch .sub{font-size:11px;color:#9db0cc;margin:0 0 10px;line-height:1.5}
.cf-dev-arch svg{width:100%;height:auto;display:block;margin:0 0 12px}
.cf-dev-arch table{width:100%;border-collapse:collapse;font-size:11px;margin:8px 0}
.cf-dev-arch th,.cf-dev-arch td{border:1px solid #455a64;padding:6px 8px;text-align:left;vertical-align:top}
.cf-dev-arch th{background:#263238;color:#aed581}
.cf-dev-arch .ok{color:#81c784}.cf-dev-arch .warn{color:#ffb74d}.cf-dev-arch .bad{color:#ef9a9a}
.cf-dev-arch code{background:#1e1e24;padding:1px 5px;border-radius:4px;font-size:10px;color:#ffcc80}
</style>
<h3>하이브리드 통신 흐름 (2026-05)</h3>
<p class="sub"><strong>Primary</strong>: R4 USB → Pi serial 데몬(:18767) → bridge(:18766). <strong>Mosquitto</strong>는 KMA·NR 등 유지. R4 farm tele/cmd는 MQTT 비의존.</p>
<svg viewBox="0 0 920 320" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="하이브리드 통신">
  <defs><marker id="arr-h" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#66bb6a"/></marker></defs>
  <rect x="20" y="120" width="110" height="50" rx="8" fill="#1b5e20" stroke="#66bb6a" stroke-width="2"/>
  <text x="75" y="142" text-anchor="middle" fill="#e8f5e9" font-size="11" font-weight="700">R4 WiFi</text>
  <text x="75" y="158" text-anchor="middle" fill="#a5d6a7" font-size="9">릴레이·RTC·I2C→R3</text>
  <rect x="20" y="200" width="110" height="44" rx="8" fill="#33691e" stroke="#aed581"/>
  <text x="75" y="226" text-anchor="middle" fill="#f1f8e9" font-size="10" font-weight="700">USB ttyACM</text>
  <line x1="75" y1="170" x2="75" y2="198" stroke="#aed581" stroke-width="2" marker-end="url(#arr-h)"/>
  <text x="75" y="188" text-anchor="middle" fill="#c5e1a5" font-size="8">tele·CMD</text>
  <rect x="160" y="200" width="130" height="44" rx="8" fill="#004d40" stroke="#4db6ac"/>
  <text x="225" y="218" text-anchor="middle" fill="#e0f2f1" font-size="10" font-weight="700">r4-serial</text>
  <text x="225" y="232" text-anchor="middle" fill="#80cbc4" font-size="9">:18767</text>
  <rect x="320" y="180" width="150" height="64" rx="8" fill="#1a237e" stroke="#7986cb" stroke-width="2"/>
  <text x="395" y="204" text-anchor="middle" fill="#e8eaf6" font-size="11" font-weight="700">sqlite_bridge</text>
  <text x="395" y="220" text-anchor="middle" fill="#c5cae9" font-size="9">ingest/tele · api/*</text>
  <text x="395" y="234" text-anchor="middle" fill="#9fa8da" font-size="9">cmd→serial API</text>
  <rect x="500" y="60" width="120" height="44" rx="8" fill="#263238" stroke="#90a4ae"/>
  <text x="560" y="86" text-anchor="middle" fill="#eceff1" font-size="10" font-weight="700">Node-RED :1880</text>
  <rect x="500" y="120" width="120" height="44" rx="8" fill="#0d47a1" stroke="#42a5f5"/>
  <text x="560" y="146" text-anchor="middle" fill="#e3f2fd" font-size="10" font-weight="700">Mosquitto</text>
  <text x="560" y="158" text-anchor="middle" fill="#90caf9" font-size="8">KMA·기타</text>
  <rect x="660" y="60" width="100" height="44" rx="8" fill="#4a148c" stroke="#ba68c8"/>
  <text x="710" y="86" text-anchor="middle" fill="#f3e5f5" font-size="10" font-weight="700">farm-ui</text>
  <rect x="660" y="180" width="100" height="44" rx="8" fill="#1b4332" stroke="#2dff7a"/>
  <text x="710" y="206" text-anchor="middle" fill="#d8ffe8" font-size="10" font-weight="700">/ui 모니터</text>
  <line x1="290" y1="222" x2="318" y2="212" stroke="#4db6ac" stroke-width="2" marker-end="url(#arr-h)"/>
  <line x1="470" y1="212" x2="498" y2="82" stroke="#7986cb" stroke-width="2" marker-end="url(#arr-h)"/>
  <line x1="470" y1="220" x2="658" y2="82" stroke="#7986cb" stroke-width="1.5" stroke-dasharray="4 3" marker-end="url(#arr-h)"/>
  <line x1="470" y1="228" x2="658" y2="202" stroke="#2dff7a" stroke-width="2" marker-end="url(#arr-h)"/>
  <line x1="130" y1="145" x2="498" y2="142" stroke="#42a5f5" stroke-width="1.5" stroke-dasharray="5 4"/>
  <text x="300" y="138" fill="#90caf9" font-size="9">롤백·옵션: MQTT tele/cmd</text>
  <line x1="130" y1="155" x2="318" y2="200" stroke="#ffb74d" stroke-width="1.5" stroke-dasharray="4 3"/>
  <text x="200" y="188" fill="#ffcc80" font-size="8">HTTP tele 백업(WiFi)</text>
</svg>
</div>"""

DEV_STATUS = r"""<div class="cf-dev-arch">
<h3>하이브리드 개발 현황</h3>
<table>
<thead><tr><th>구성요소</th><th>저장소</th><th>Pi 적용</th></tr></thead>
<tbody>
<tr><td>USB serial 데몬</td><td class="ok">cronusfarm_r4_serial_daemon.py</td><td class="warn">pi-install-r4-serial-primary.sh</td></tr>
<tr><td>펌웨어 USB cmd</td><td class="ok">CRONUSFARM_MQTT_ENABLE 0 옵션</td><td class="warn">secrets.h + pi-upload-r4.sh</td></tr>
<tr><td>브리지 cmd→serial</td><td class="ok">CRONUSFARM_R4_CMD_TRANSPORT=serial</td><td class="warn">systemd drop-in</td></tr>
<tr><td>업로드 락</td><td class="ok">r4-upload.lock</td><td class="warn">업로드 시 데몬 stop</td></tr>
<tr><td>MQTT 롤백</td><td class="ok">pi-enable-r4-mqtt-fallback.sh</td><td>—</td></tr>
<tr><td>Git 백업</td><td class="ok">feature/r4-usb-serial-primary</td><td class="warn">git pull 후 설치</td></tr>
</tbody>
</table>
<p class="sub">브랜치 <code>feature/r4-usb-serial-primary</code> · 태그 <code>backup/pre-usb-serial-20260525</code> · 문서 <code>docs/cronusfarm_r4_usb_serial.md</code></p>
</div>"""

MQTT_ROOT = r"""<div class="cf-dev-arch">
<h3>MQTT offline 근본 원인 (점검)</h3>
<table>
<thead><tr><th>원인</th><th>증상</th><th>조치</th></tr></thead>
<tbody>
<tr><td>① R4 MQTT_HOST 오설정</td><td>WiFi OK·MQTT만 실패</td><td>secrets.h = Pi <strong>LAN IP</strong> (Tailscale/mDNS X)</td></tr>
<tr><td>② WiFi 블로킹 재연결</td><td>tele 수백~수천초 stale</td><td>2.4G 고정·AP 격리 OFF·USB primary 전환</td></tr>
<tr><td>③ retain online 오탐</td><td>status online·tele 없음</td><td>tele_stale·mosquitto_sub로 검증</td></tr>
<tr><td>④ 시리얼 DTR 리셋</td><td>업로드/프로비저닝 직후 끊김</td><td>120초 대기·DTR off·mqtt-watch 중지</td></tr>
<tr><td>⑤ clientId 충돌</td><td>간헐 끊김</td><td>DEVICE_ID 1대·재연결 ID 로테이션</td></tr>
</tbody>
</table>
<p class="sub">체크리스트만으로 MQTT가 안 되면 <strong>USB primary</strong>로 farm 서비스 복구 후, MQTT는 KMA·모니터용으로만 유지.</p>
<p class="sub">Pi: <code>bash scripts/pi-recover-r4-usb.sh</code> · <code>curl -s http://127.0.0.1:18767/health</code> · <code>api/time/status?device_id=cronusfarm-01</code></p>
</div>"""

OFFLINE_CHECK = r"""<div class="cf-dev-arch">
<h3>MQTT offline 시 영향</h3>
<table>
<thead><tr><th>항목</th><th>MQTT만</th><th>USB primary 적용 후</th></tr></thead>
<tbody>
<tr><td>R4 tele→DB</td><td class="bad">중단</td><td class="ok">복구</td></tr>
<tr><td>스케줄·RTC·채널 cmd</td><td class="bad">중단</td><td class="ok">복구</td></tr>
<tr><td>farm-ui r4_online</td><td class="bad">offline</td><td class="ok">bridge API 기준</td></tr>
<tr><td>NR MQTT 탭 tele</td><td class="bad">없음</td><td class="warn">republish=1 시만</td></tr>
<tr><td>R4 로컬 스케줄·패널</td><td class="ok">동작</td><td class="ok">동작</td></tr>
<tr><td>Hailo·텔레·OAuth</td><td class="ok">무관</td><td class="ok">무관</td></tr>
</tbody>
</table>
</div>"""

TPL_SPECS = (
    ("ui_tpl_devflow_hybrid_flow", "개발환경: 하이브리드 통신", 0, 8, HYBRID_FLOW),
    ("ui_tpl_devflow_dev_status", "개발환경: 개발 현황", 1, 6, DEV_STATUS),
    ("ui_tpl_devflow_mqtt_root", "개발환경: MQTT 근본원인", 2, 7, MQTT_ROOT),
    ("ui_tpl_devflow_offline_chk", "개발환경: offline 영향", 3, 6, OFFLINE_CHECK),
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

    max_order = 0
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
                "y": 40 + order * 50,
                "wires": [[]],
            }
            by_id[tid] = node
        node["format"] = fmt
        node["order"] = order
        node["height"] = height
        node["group"] = grp
        max_order = max(max_order, order)

    bump_ids = {tid for tid, _, _, _, _ in TPL_SPECS}
    for n in by_id.values():
        if n.get("type") != "ui_template" or n.get("group") != grp:
            continue
        tid = n.get("id")
        if tid in bump_ids:
            continue
        o = int(n.get("order") or 99)
        if o <= max_order:
            n["order"] = o + len(TPL_SPECS)

    DEVFLOW.write_text(json.dumps(list(by_id.values()), ensure_ascii=False), encoding="utf-8")
    print(f"OK {DEVFLOW.name} hybrid/usb panels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
