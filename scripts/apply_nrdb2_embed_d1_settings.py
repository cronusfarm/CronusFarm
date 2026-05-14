# D1 /ui 설정 탭에 NRDB2 스케줄·관제(동일 템플릿) iframe으로 포함 + NRDB2 전용 페이지 /schedule-ctl 생성
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "nodered" / "flows_cronusfarm_devflow_flow.json"
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"


def main() -> None:
    dev = json.loads(DEV.read_text(encoding="utf-8-sig"))
    dash = json.loads(DASH.read_text(encoding="utf-8-sig"))
    dev_changed = False
    dash_changed = False

    if not any(n.get("id") == "cf_nrdb2_page_schedhub" for n in dev):
        idx = next(i for i, n in enumerate(dev) if n.get("id") == "f1e2d3c4b5a68003")
        ref = dev[idx]
        br = ref.get("breakpoints") or []
        new_page = {
            "id": "cf_nrdb2_page_schedhub",
            "type": "ui-page",
            "name": "스케줄·관제",
            "ui": "f1e2d3c4b5a68002",
            "path": "/schedule-ctl",
            "icon": "calendar-clock",
            "layout": "grid",
            "theme": ref.get("theme"),
            "breakpoints": copy.deepcopy(br),
            "order": 2,
            "className": "nrdb-settings-page",
            "visible": "true",
            "disabled": "false",
        }
        g_sched = {
            "id": "cf_nrdb2_grp_sched",
            "type": "ui-group",
            "name": "스케줄 변경하기",
            "page": "cf_nrdb2_page_schedhub",
            "width": "12",
            "height": "1",
            "order": 1,
            "showTitle": True,
            "className": "",
            "visible": "true",
            "disabled": "false",
            "groupType": "default",
        }
        g_hub = {
            "id": "cf_nrdb2_grp_hub",
            "type": "ui-group",
            "name": "관제 허브 — 환경 목표·임계 (SQLite)",
            "page": "cf_nrdb2_page_schedhub",
            "width": "12",
            "height": "1",
            "order": 2,
            "showTitle": True,
            "className": "",
            "visible": "true",
            "disabled": "false",
            "groupType": "default",
        }
        dev[idx + 1 : idx + 1] = [new_page, g_sched, g_hub]
        dev_changed = True
        print("devflow: +cf_nrdb2_page_schedhub +2 groups")

    if not any(n.get("id") == "cf_nrdb2_t_sched_clone" for n in dash):
        sched = next(n for n in dash if n.get("id") == "f1e2d3c4b5a6f020")
        hub = next(n for n in dash if n.get("id") == "f1e2d3c4b5a6f022")
        ns = copy.deepcopy(sched)
        ns["id"] = "cf_nrdb2_t_sched_clone"
        ns["group"] = "cf_nrdb2_grp_sched"
        ns["name"] = "스케줄 변경 UI (NRDB2·/ui 포함용)"
        nh = copy.deepcopy(hub)
        nh["id"] = "cf_nrdb2_t_hub_clone"
        nh["group"] = "cf_nrdb2_grp_hub"
        nh["name"] = "NRDB2 관제 허브 (NRDB2·/ui 포함용)"
        dash.extend([ns, nh])
        dash_changed = True
        print("dashboard: +cf_nrdb2_t_sched_clone +cf_nrdb2_t_hub_clone")

    if not any(n.get("id") == "ui_grp_nrdb2_shell" for n in dash):
        grp = {
            "id": "ui_grp_nrdb2_shell",
            "type": "ui_group",
            "name": "스케줄·관제 (NRDB2)",
            "tab": "ui_tab_settings",
            "order": 7,
            "disp": True,
            "width": "12",
            "collapse": False,
            "className": "",
        }
        fmt = """<div class="cf-nrdb2-wrap" style="box-sizing:border-box;width:100%;">
<style>
.cf-nrdb2-wrap iframe { display:block; width:100%; min-height:1120px; border:0; border-radius:16px; box-shadow:0 8px 32px rgba(0,0,0,.35); background:#070c15; }
@media (max-width:600px){ .cf-nrdb2-wrap iframe { min-height:900px; } }
</style>
<p style="margin:0 0 10px;font-size:13px;color:#9db0cc;line-height:1.55;font-family:system-ui,'Malgun Gothic',sans-serif;">
  아래는 <strong style="color:#81c784">Dashboard 2</strong>와 동일한 화면입니다. <strong style="color:#81c784">스케줄 변경하기</strong> · <strong style="color:#81c784">관제 허브</strong>만 모았습니다. 스크롤은 프레임 안에서 하면 됩니다.
  <span style="opacity:.85">(직접 열기: <code style="color:#ffcc80">/nrdb2/schedule-ctl</code>)</span>
</p>
<iframe title="NRDB2 스케줄·관제" src="/nrdb2/schedule-ctl"></iframe>
</div>"""
        tpl = {
            "id": "ui_tpl_nrdb2_in_settings",
            "type": "ui_template",
            "z": "tab_cronus_dash",
            "group": "ui_grp_nrdb2_shell",
            "name": "NRDB2 스케줄·관제(iframe)",
            "order": 1,
            "width": "12",
            "height": "28",
            "format": fmt,
            "storeOutMessages": False,
            "fwdInMessages": False,
            "resendOnRefresh": True,
            "templateScope": "local",
            "x": 200,
            "y": 1200,
            "wires": [[]],
        }
        dash.extend([grp, tpl])
        dash_changed = True
        print("dashboard: +ui_grp_nrdb2_shell +ui_tpl_nrdb2_in_settings")

    if dev_changed:
        DEV.write_text(json.dumps(dev, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if dash_changed:
        DASH.write_text(json.dumps(dash, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if not dev_changed and not dash_changed:
        print("no changes (already applied)")


if __name__ == "__main__":
    main()
