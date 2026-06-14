# -*- coding: utf-8 -*-
"""09:00 아침 브리핑 / 17:00 저녁 영농일지 분리.

원인: cf_inj_tg_news_daily(09:00)와 cf_inj_tg_news_evening(17:00)가
      동일 cf_fn_tg_news_daily(🌙 저녁 템플릿)에 연결됨.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW_PATHS = [
    ROOT / "nodered" / "merged-deploy.json",
    ROOT / "nodered" / "flows_cronusfarm_dashboard.json",
    ROOT / "nodered" / "flows_cronusfarm_mqtt.json",
]

FN_EXEC_MORNING = r"""// 아침(09:00) — Open-Meteo·KMA 통합 템플릿 (pi-send-telegram-briefings.py)
const cp = global.get('child_process');
if (!cp) {
  node.error('child_process 없음 — scripts/pi-nodered-patch-child-process-context.sh');
  return null;
}
const root = (env.get('CRONUSFARM_ROOT') || '/home/dooly/CronusFarm').toString().trim();
const cmd = "bash -lc 'set -a; [ -f /etc/cronusfarm/nodered-telegram.env ] && . /etc/cronusfarm/nodered-telegram.env; set +a; python3 "
  + root + "/scripts/pi-send-telegram-briefings.py morning'";
try {
  const out = cp.execSync(cmd, { encoding: 'utf8', maxBuffer: 2 * 1024 * 1024, timeout: 120000 });
  node.log('아침 브리핑 OK: ' + String(out || '').trim().slice(0, 120));
} catch (e) {
  node.error('아침 브리핑 실패: ' + String(e.message || e));
}
return null;"""


def patch_flow(path: Path) -> list[str]:
    if not path.is_file():
        return []
    flows = json.loads(path.read_text(encoding="utf-8-sig"))
    ids = {n.get("id") for n in flows if isinstance(n, dict)}
    changed: list[str] = []
    tab = "b1c5a1f1d7a2a3a1"

    if "cf_fn_tg_briefing_morning" not in ids:
        for n in flows:
            if n.get("id") == "cf_inj_tg_news_daily":
                tab = n.get("z", tab)
                break
        flows.append(
            {
                "id": "cf_fn_tg_briefing_morning",
                "type": "function",
                "z": tab,
                "name": "아침 브리핑(09:00 exec)",
                "func": FN_EXEC_MORNING,
                "outputs": 0,
                "timeout": 0,
                "noerr": 0,
                "initialize": "",
                "finalize": "",
                "libs": [],
                "x": 420,
                "y": 1420,
                "wires": [[]],
            }
        )
        changed.append("cf_fn_tg_briefing_morning")

    for n in flows:
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        if nid == "cf_inj_tg_news_daily":
            n["name"] = "텔레그램 아침(매일 09:00)"
            w = n.get("wires") or [[]]
            if w and w[0] != ["cf_fn_tg_briefing_morning"]:
                n["wires"] = [["cf_fn_tg_briefing_morning"]]
                changed.append("cf_inj_tg_news_daily→morning")
        elif nid == "cf_inj_tg_news_now":
            n["name"] = "텔레그램 아침(지금 테스트)"
            w = n.get("wires") or [[]]
            if w and w[0] != ["cf_fn_tg_briefing_morning"]:
                n["wires"] = [["cf_fn_tg_briefing_morning"]]
                changed.append("cf_inj_tg_news_now→morning")
        elif nid == "cf_inj_tg_news_evening":
            n["name"] = "텔레그램 저녁(매일 17:00)"
            w = n.get("wires") or [[]]
            if w and w[0] != ["cf_fn_tg_news_evening"]:
                n["wires"] = [["cf_fn_tg_news_evening"]]
                changed.append("cf_inj_tg_news_evening wire")
        elif nid == "cf_fn_tg_news_daily":
            n["id"] = "cf_fn_tg_news_evening"
            n["name"] = "저녁 영농일지 준비"
            changed.append("rename cf_fn_tg_news_daily→evening")
        elif nid == "cf_fn_tg_news_evening" and n.get("name") == "뉴스 메시지 준비":
            n["name"] = "저녁 영농일지 준비"

    # id rename: fix wires still pointing to old id
    for n in flows:
        if not isinstance(n, dict):
            continue
        wires = n.get("wires")
        if not wires:
            continue
        new_wires = []
        for row in wires:
            new_row = []
            for wid in row:
                if wid == "cf_fn_tg_news_daily":
                    new_row.append("cf_fn_tg_news_evening")
                else:
                    new_row.append(wid)
            new_wires.append(new_row)
        if new_wires != wires:
            n["wires"] = new_wires

    if changed:
        path.write_text(
            json.dumps(flows, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return changed


def main() -> None:
    for p in FLOW_PATHS:
        ch = patch_flow(p)
        if ch:
            print(f"OK {p.name}: {', '.join(ch)}")
        else:
            print(f"skip {p.name}")


if __name__ == "__main__":
    main()
