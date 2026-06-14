# -*- coding: utf-8 -*-
"""Farm 환경 카드(ui_tpl_farm_env)를 백업 템플릿으로 복원."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
FMT_TXT = Path(__file__).resolve().parent / "_farm_env_fmt.txt"


def main() -> int:
    if not FMT_TXT.is_file():
        raise SystemExit(f"missing: {FMT_TXT}")
    fmt = FMT_TXT.read_text(encoding="utf-8", errors="replace")
    if "기상청 KMA" not in fmt:
        raise SystemExit("backup fmt does not contain KMA")

    data = json.loads(DASH.read_text(encoding="utf-8-sig"))
    by = {n["id"]: n for n in data if isinstance(n, dict) and n.get("id")}
    n = by.get("ui_tpl_farm_env")
    if not isinstance(n, dict):
        raise SystemExit("ui_tpl_farm_env not found")

    n["format"] = fmt
    n["width"] = "12"
    # 행 수에 맞춰 대략 높이(그리드 단) 확보: KMA(6행)+온실(2행)+헤더/여백
    n["height"] = max(int(n.get("height") or 0), 11)

    DASH.write_text(json.dumps(list(by.values()), ensure_ascii=False), encoding="utf-8")
    print("OK patch_farm_env_restore")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

