#!/usr/bin/env python3
import json
import re
from pathlib import Path

p = Path("/home/dooly/.node-red/flows.json")
d = json.loads(p.read_text(encoding="utf-8"))
for n in d:
    f = n.get("format") or ""
    if "cf-monitor-tab-clock" not in f and "#clock" not in f and "cf-sidebar-clock" not in f:
        continue
    nid = n.get("id", "?")
    print("---", nid, n.get("name", ""), n.get("type"))
    print("  fmtKstNow:", "fmtKstNow" in f)
    print("  kstParts:", "kstParts" in f)
    print("  getHours():", "getHours()" in f)
    print("  legacy toLocale:", bool(
        re.search(r'toLocaleString\(["\']ko-KR["\']', f) and "fmtKstNow" not in f
    ))
    if "__cfMonitorToolbarClock" in f:
        print("  toolbar boot: yes")
