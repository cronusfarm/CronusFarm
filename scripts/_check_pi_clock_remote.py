#!/usr/bin/env python3
import json
import re
from pathlib import Path

p = Path("/home/dooly/.node-red/flows.json")
d = json.loads(p.read_text(encoding="utf-8"))
for nid in ("nr_node_ui_ai_stream", "ui_tpl_css_cronus"):
    n = [x for x in d if x.get("id") == nid]
    if not n:
        print(nid, "MISSING")
        continue
    f = n[0].get("format") or ""
    print("===", nid)
    print("  fmtKstNow:", "fmtKstNow" in f)
    print("  __cfMonitorToolbarClock:", "__cfMonitorToolbarClock" in f)
    if re.search(r'toLocaleString\(["\']ko-KR["\']', f) and "fmtKstNow" not in f:
        print("  LEGACY toLocaleString in this node: YES")
    i = f.find("function tick")
    if i >= 0:
        print(f[i : i + 450])
