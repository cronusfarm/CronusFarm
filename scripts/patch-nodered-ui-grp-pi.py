import json
from pathlib import Path


def main() -> int:
    p = Path("/home/dooly/.node-red/flows.json")
    objs = json.loads(p.read_text(encoding="utf-8"))

    ids = {o.get("id") for o in objs if isinstance(o, dict) and o.get("id")}

    changed = 0
    for o in objs:
        if isinstance(o, dict) and o.get("type") == "ui_group" and o.get("id") == "ui_grp_pi":
            if o.get("name") != "System (Pi : ida)":
                o["name"] = "System (Pi : ida)"
                changed += 1
            # 모니터 탭 2컬럼(오른쪽) 배치
            if o.get("width") != "6":
                o["width"] = "6"
                changed += 1
            if o.get("order") != 2:
                o["order"] = 2
                changed += 1

        if isinstance(o, dict) and o.get("type") == "ui_group" and o.get("id") == "ui_grp_arduino":
            # 모니터 탭 2컬럼(오른쪽) 배치
            if o.get("width") != "6":
                o["width"] = "6"
                changed += 1
            if o.get("order") != 4:
                o["order"] = 4
                changed += 1

        if isinstance(o, dict) and o.get("type") == "ui_group" and o.get("id") == "ui_grp_a":
            # 모니터 탭 2컬럼(왼쪽) 배치
            if o.get("width") != "6":
                o["width"] = "6"
                changed += 1
            if o.get("order") != 1:
                o["order"] = 1
                changed += 1

        if isinstance(o, dict) and o.get("type") == "ui_group" and o.get("id") == "ui_grp_b":
            # 모니터 탭 2컬럼(왼쪽) 배치
            if o.get("width") != "6":
                o["width"] = "6"
                changed += 1
            if o.get("order") != 3:
                o["order"] = 3
                changed += 1
        if isinstance(o, dict) and o.get("type") == "ui_text" and o.get("id") == "ui_txt_uptime":
            if o.get("label") != "Booting Time":
                o["label"] = "Booting Time"
                changed += 1
        if isinstance(o, dict) and o.get("type") == "ui_text" and o.get("id") == "ui_txt_pi_host":
            # Pi 그룹 표시 순서 고정(서비스는 아래)
            if o.get("order") != 5:
                o["order"] = 5
                changed += 1

        # ------------------------------------------------------------
        # Pi 그룹(ui_grp_pi) 순서:
        # Booting Time / SSID / IP / Tailscale IP / Pi 도메인 / Pi tick / Node-RED / Mosquitto
        if isinstance(o, dict) and o.get("group") == "ui_grp_pi":
            order_map = {
                "ui_txt_uptime": 1,
                "ui_txt_ssid": 2,
                "ui_txt_ip": 3,
                "ui_txt_ts_ip": 4,
                "ui_txt_pi_host": 5,
                "ui_txt_pi_tick": 6,
                "ui_tpl_pi_nodered": 7,
                "ui_tpl_pi_mosq": 8,
            }
            oid = o.get("id")
            if oid in order_map and o.get("order") != order_map[oid]:
                o["order"] = order_map[oid]
                changed += 1

        # ------------------------------------------------------------
        # Arduino 그룹(ui_grp_arduino)도 서비스(데몬) 정보는 아래에 배치
        if isinstance(o, dict) and o.get("group") == "ui_grp_arduino":
            order_map = {
                # 사용자 요청 순서:
                # 1) Arduino R4 WiFi SSID
                # 2) Arduino R4 IP
                # 3) Arduino R4 연결 online
                # 4) tele(요약)
                # 5) Arduino Mega 연결
                # 6) MQTT status(raw) online
                # 7) tele(raw)
                # 8) cmd(미리보기)
                "ui_txt_arduino_wifi_ssid": 1,
                "ui_txt_arduino_wifi_ip": 2,
                "ui_tpl_conn_line": 3,
                "ui_tpl_tele_summary": 4,
                "ui_tpl_status_line": 5,  # Arduino R4 MQTT(서비스 성격)
                "ui_txt_tele_raw": 6,     # tele(raw) (R4 MQTT 아래)
                "ui_txt_status_raw": 7,   # MQTT status(raw)
                "ui_txt_cmd_preview": 8,  # cmd(미리보기)
                "ui_tpl_mega_conn": 9,    # Arduino Mega 연결(UART) → R4 MQTT 관련 아래
            }
            oid = o.get("id")
            if oid in order_map and o.get("order") != order_map[oid]:
                o["order"] = order_map[oid]
                changed += 1

            # 라벨/타이틀 정리
            if oid == "ui_txt_arduino_wifi_ssid":
                if o.get("label") != "Arduino R4 WiFi SSID":
                    o["label"] = "Arduino R4 WiFi SSID"
                    changed += 1
                # 항목 분리(한 줄에 하나씩)
                if o.get("width") != 12:
                    o["width"] = 12
                    changed += 1
            if oid == "ui_txt_arduino_wifi_ip":
                if o.get("label") != "Arduino R4 IP":
                    o["label"] = "Arduino R4 IP"
                    changed += 1
                # 항목 분리(한 줄에 하나씩)
                if o.get("width") != 12:
                    o["width"] = 12
                    changed += 1
            if oid == "ui_txt_status_raw" and "format" in o:
                if "MQTT status(raw)" not in o["format"]:
                    o["format"] = o["format"].replace("status(raw)", "MQTT status(raw)")
                    changed += 1
            if oid == "ui_tpl_conn_line" and "format" in o:
                # "Arduino 연결" → "Arduino R4 연결"
                if "Arduino R4 연결" not in o["format"]:
                    o["format"] = o["format"].replace("Arduino 연결", "Arduino R4 연결")
                    changed += 1
                # 같은 이름 충돌 방지: 연결 카드 안의 tele(요약) 표기를 다른 이름으로 변경
                if "tele(요약)" in o["format"]:
                    o["format"] = o["format"].replace("tele(요약)", "tele(미리보기)")
                    changed += 1
                # 미리보기 영역이 짤리지 않도록(줄바꿈 + 스크롤 + 최소 높이)
                if "cf-tele-preview" in o["format"] and "max-height" not in o["format"]:
                    o["format"] = o["format"].replace(
                        "<pre>{{msg.telePreview}}</pre>",
                        "<pre style=\"white-space:pre-wrap;max-height:140px;min-height:84px;overflow:auto;\">{{msg.telePreview}}</pre>",
                    )
                    changed += 1

            if oid == "ui_tpl_status_line" and "format" in o:
                # MQTT 담당이 R4이므로 라벨을 Arduino R4 MQTT로 명확히
                if "Arduino R4 MQTT" not in o["format"]:
                    o["format"] = o["format"].replace("Arduino MQTT", "Arduino R4 MQTT")
                    changed += 1

    # ------------------------------------------------------------
    # Arduino 그룹: tele(요약) 위젯 추가(없으면 생성) + mqtt_in_tele에서 메시지 전달
    if "ui_tpl_tele_summary" not in ids:
        # ui_template 노드(정적 스타일 유지)
        objs.append(
            {
                "id": "ui_tpl_tele_summary",
                "type": "ui_template",
                "z": "tab_cronus_dash",
                "group": "ui_grp_arduino",
                "name": "tele(요약)",
                "order": 4,
                "width": "12",
                "height": 0,
                "format": "<div class=\"cf-raw\"><div class=\"cf-raw-title\">tele(요약-실시간)</div><pre>{{(msg.payload||'').toString().slice(0,320)}}{{(msg.payload||'').toString().length>320 ? '…' : ''}}</pre></div>",
                "storeOutMessages": False,
                "fwdInMessages": True,
                "resendOnRefresh": True,
                "templateScope": "local",
                "className": "",
            }
        )
        ids.add("ui_tpl_tele_summary")
        changed += 1
    else:
        for o in objs:
            if isinstance(o, dict) and o.get("id") == "ui_tpl_tele_summary" and "format" in o:
                if "tele(요약-실시간)" not in o["format"]:
                    o["format"] = o["format"].replace("tele(요약)", "tele(요약-실시간)")
                    changed += 1
                # 길이 확장(200 → 320)
                if ".slice(0,200)" in o["format"] or "length>200" in o["format"]:
                    o["format"] = (
                        o["format"]
                        .replace(".slice(0,200)", ".slice(0,320)")
                        .replace("length>200", "length>320")
                    )
                    changed += 1

    if "ui_tpl_mega_conn" not in ids:
        # 현재는 UART 상태를 직접 측정하지 않으므로, 안내 카드(정적)로 제공
        objs.append(
            {
                "id": "ui_tpl_mega_conn",
                "type": "ui_template",
                "z": "tab_cronus_dash",
                "group": "ui_grp_arduino",
                "name": "Arduino Mega 연결",
                "order": 5,
                "width": "12",
                "height": 0,
                "format": "<div class=\"cf-row cf-arduino-conn\"><div class=\"cf-label\">Arduino Mega 연결</div><div style=\"display:flex;align-items:center;gap:10px;flex-shrink:0;\"><div class=\"cf-dot\" ng-class=\"(msg.payload||'').toString().indexOf('M:mega=1')>=0 ? 'cf-dot-on' : 'cf-dot-off'\"></div><div style=\"font-size:12px;color:var(--cf-text);white-space:nowrap;\">{{(msg.payload||'').toString().indexOf('M:mega=1')>=0 ? 'online' : 'offline'}}</div><div class=\"cf-muted\" style=\"font-size:12px;white-space:nowrap;\">UART(0/1)</div></div></div><div class=\"cf-raw\" style=\"margin-top:6px;\"><div class=\"cf-raw-title\">패널(P)</div><pre style=\"white-space:pre-wrap;max-height:90px;overflow:auto;\">{{(msg.payload||'').toString().match(/\\|\\s*P:[^|]*/)? (msg.payload||'').toString().match(/\\|\\s*P:[^|]*/)[0].trim() : '(없음)'}} </pre></div>",
                "storeOutMessages": False,
                "fwdInMessages": False,
                "resendOnRefresh": True,
                "templateScope": "local",
                "className": "",
            }
        )
        ids.add("ui_tpl_mega_conn")
        changed += 1
    else:
        for o in objs:
            if isinstance(o, dict) and o.get("id") == "ui_tpl_mega_conn" and "format" in o:
                # 한 줄 표시 + 패널(P) 정보 출력
                new_fmt = "<div class=\\\"cf-row cf-arduino-conn\\\"><div class=\\\"cf-label\\\">Arduino Mega 연결</div><div style=\\\"display:flex;align-items:center;gap:10px;flex-shrink:0;\\\"><div class=\\\"cf-dot\\\" ng-class=\\\"(msg.payload||'').toString().indexOf('M:mega=1')>=0 ? 'cf-dot-on' : 'cf-dot-off'\\\"></div><div style=\\\"font-size:12px;color:var(--cf-text);white-space:nowrap;\\\">{{(msg.payload||'').toString().indexOf('M:mega=1')>=0 ? 'online' : 'offline'}}</div><div class=\\\"cf-muted\\\" style=\\\"font-size:12px;white-space:nowrap;\\\">UART(0/1)</div></div></div><div class=\\\"cf-raw\\\" style=\\\"margin-top:6px;\\\"><div class=\\\"cf-raw-title\\\">패널(P)</div><pre style=\\\"white-space:pre-wrap;max-height:90px;overflow:auto;\\\">{{(msg.payload||'').toString().match(/\\\\|\\\\s*P:[^|]*/)? (msg.payload||'').toString().match(/\\\\|\\\\s*P:[^|]*/)[0].trim() : '(없음)'}} </pre></div>"
                if o["format"] != new_fmt:
                    o["format"] = new_fmt
                    changed += 1

    # mqtt_in_tele가 ui_txt_tele_raw로 직접 쏘는 구조이므로, tele(요약)도 같은 입력을 받게 wires에 추가
    for o in objs:
        if isinstance(o, dict) and o.get("id") == "mqtt_in_tele" and isinstance(o.get("wires"), list):
            if len(o["wires"]) == 0:
                o["wires"] = [[]]
            out0 = o["wires"][0]
            if "ui_tpl_tele_summary" not in out0:
                out0.append("ui_tpl_tele_summary")
                changed += 1
            if "ui_tpl_mega_conn" in ids and "ui_tpl_mega_conn" not in out0:
                out0.append("ui_tpl_mega_conn")
                changed += 1

        # ------------------------------------------------------------
        # (구) 슬라이드 스위치 제거/대체: "CronusFarm MQTT" 탭의 펌프 ui_switch → 카드 토글로 대체
        if isinstance(o, dict) and o.get("type") == "ui_switch" and o.get("id") == "c7b2b8e7cc1b92a1":
            # 슬라이드 스위치 UI는 숨김(기능은 카드가 대체)
            if o.get("className") != "cf-hide":
                o["className"] = "cf-hide"
                changed += 1
            if o.get("width") != 0:
                o["width"] = 0
                changed += 1

    # 카드 토글(ui_template) 추가(없으면 생성)
    if "ui_tpl_toggle_pump_mqtt" not in ids:
        objs.append(
            {
                "id": "ui_tpl_toggle_pump_mqtt",
                "type": "ui_template",
                "z": "b1c5a1f1d7a2a3a1",  # CronusFarm MQTT 탭(플로우)
                "group": "d1f9b55a9843c0a1",
                "name": "펌프 토글(카드)",
                "order": 1,
                "width": "6",
                "height": 0,
                "format": "<div class=\"cf-tile\" style=\"cursor:pointer;\" ng-click=\"send({topic:'', payload: ((msg.payload||'0').toString().trim()==='1') ? '0' : '1'})\"><div class=\"cf-tile-left\"><div class=\"cf-tile-txt\"><div class=\"cf-tile-name\">펌프</div><div class=\"cf-tile-sub\">탭해서 토글</div></div></div><div class=\"cf-tile-right\"><div class=\"cf-pill\" ng-class=\"((msg.payload||'0').toString().trim()==='1') ? 'cf-on' : 'cf-off'\">{{((msg.payload||'0').toString().trim()==='1') ? 'ON' : 'OFF'}}</div></div></div>",
                "storeOutMessages": False,
                "fwdInMessages": True,
                "resendOnRefresh": True,
                "templateScope": "local",
                "className": "",
                "wires": [["c2d5b8a8b3cc12a1"]],
            }
        )
        ids.add("ui_tpl_toggle_pump_mqtt")
        changed += 1

    p.write_text(json.dumps(objs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"changed={changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

