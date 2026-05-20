# -*- coding: utf-8 -*-
import json
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "nodered" / "flows_cronusfarm_dashboard.json"
d = json.loads(p.read_text(encoding="utf-8-sig"))
for x in d:
    if x.get("id") == "ui_tpl_farm_env":
        Path(__file__).parent.joinpath("_farm_env_fmt.txt").write_text(
            x.get("format", ""), encoding="utf-8"
        )
        print("written _farm_env_fmt.txt", len(x.get("format", "")))
        break
