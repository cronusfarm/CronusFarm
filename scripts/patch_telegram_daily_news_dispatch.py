# -*- coding: utf-8 -*-
"""append_telegram_daily_news.py 의 FN_PREP를 flows JSON에 반영."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
flow = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
src = (ROOT / "scripts" / "append_telegram_daily_news.py").read_text(encoding="utf-8")
m = re.search(r'FN_PREP = """(.*?)"""', src, re.DOTALL)
if not m:
    raise SystemExit("FN_PREP not found in append_telegram_daily_news.py")
new_func = m.group(1)
flows = json.loads(flow.read_text(encoding="utf-8"))
found = False
for n in flows:
    if not isinstance(n, dict):
        continue
    if n.get("id") == "cf_fn_tg_news_daily":
        n["func"] = new_func
        found = True
if not found:
    raise SystemExit("cf_fn_tg_news_daily not in flows")
flow.write_text(json.dumps(flows, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
print("OK patched", flow)
