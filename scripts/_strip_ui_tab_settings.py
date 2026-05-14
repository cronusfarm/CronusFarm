# CronusFarm-설정(ui_tab_settings) 탭의 그룹·위젯 전부 제거 + 연결 정리
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
TAB = "ui_tab_settings"


def main() -> None:
    nodes = json.loads(DASH.read_text(encoding="utf-8-sig"))
    grps = [n for n in nodes if n.get("type") == "ui_group" and n.get("tab") == TAB]
    gids = {g["id"] for g in grps}
    remove: set[str] = set(gids)
    for n in nodes:
        if n.get("group") in gids:
            remove.add(n["id"])

    kept: list = []
    for n in nodes:
        if n["id"] in remove:
            continue
        wires = n.get("wires")
        if isinstance(wires, list):
            new_w = []
            for outs in wires:
                if not isinstance(outs, list):
                    new_w.append(outs)
                    continue
                filt = [t for t in outs if t not in remove]
                new_w.append(filt)
            n["wires"] = new_w
        kept.append(n)

    DASH.write_text(json.dumps(kept, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("removed", len(remove), "nodes; kept", len(kept))


if __name__ == "__main__":
    main()
