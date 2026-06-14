# PHW3988 대시보드: 별도 탭 제거 → 모니터 탭 Farm 흐름 아래 "센서 Data" 그룹으로 통합
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD_TAB = "acb49c1191b0b7f3"
OLD_G1 = "6df0ea00c921dbea"
OLD_G2 = "aa20202e1f1cb24e"
NEW_GH = "ui_grp_gh_data"
MON_TAB = "ui_tab_monitor"
DROP_IDS = {OLD_TAB, OLD_G1, OLD_G2}
OLD_GROUPS = {OLD_G1, OLD_G2}


def jdump(path: Path, data: list) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def patch_dashboard(nodes: list) -> list:
    out = [n for n in nodes if n.get("id") not in DROP_IDS]
    for n in out:
        if n.get("id") == "ui_grp_pi" and n.get("type") == "ui_group":
            n["order"] = 7
        if n.get("id") == "ui_grp_arduino" and n.get("type") == "ui_group":
            n["order"] = 8
    out.append(
        {
            "id": NEW_GH,
            "type": "ui_group",
            "name": "양액 상태 Data",
            "tab": MON_TAB,
            "order": 6,
            "disp": True,
            "width": "12",
            "collapse": False,
            "className": "",
        }
    )
    return out


def patch_devflow(nodes: list) -> list:
    for n in nodes:
        g = n.get("group")
        if g in OLD_GROUPS:
            n["group"] = NEW_GH
    return nodes


def patch_pi(nodes: list) -> list:
    out = [n for n in nodes if n.get("id") not in DROP_IDS]
    for n in out:
        if n.get("id") == "ui_grp_pi" and n.get("type") == "ui_group":
            n["order"] = 7
        if n.get("id") == "ui_grp_arduino" and n.get("type") == "ui_group":
            n["order"] = 8
        if n.get("group") in OLD_GROUPS:
            n["group"] = NEW_GH
    if not any(n.get("id") == NEW_GH for n in out):
        out.append(
            {
                "id": NEW_GH,
                "type": "ui_group",
                "name": "양액 상태 Data",
                "tab": MON_TAB,
                "order": 6,
                "disp": True,
                "width": "12",
                "collapse": False,
                "className": "",
            }
        )
    return out


def main() -> None:
    dash_p = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
    dev_p = ROOT / "nodered" / "flows_cronusfarm_devflow_flow.json"
    pi_p = ROOT / "nodered" / "flows_pi_editor_latest.json"

    d1 = json.loads(dash_p.read_text(encoding="utf-8-sig"))
    jdump(dash_p, patch_dashboard(d1))

    d2 = json.loads(dev_p.read_text(encoding="utf-8-sig"))
    jdump(dev_p, patch_devflow(d2))

    if pi_p.is_file():
        d3 = json.loads(pi_p.read_text(encoding="utf-8-sig"))
        d3 = patch_pi(d3)
        pi_p.write_text(json.dumps(d3, ensure_ascii=False, indent=4), encoding="utf-8")

    print("patched dashboard, devflow" + (", pi export" if pi_p.is_file() else ""))


if __name__ == "__main__":
    main()
