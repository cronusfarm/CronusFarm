#!/usr/bin/env python3
import json
from pathlib import Path

p = Path("/home/dooly/.node-red/flows.json")
d = json.loads(p.read_text(encoding="utf-8"))
for n in d:
    f = n.get("format") or ""
    if "cf-monitor-tab-clock" in f:
        i = f.find("function tick")
        print("=== toolbar cf-monitor-tab-clock ===")
        print(f[i : i + 550])
    if n.get("id") == "ui_tpl_shell_html":
        print("=== ui_tpl_shell_html ===")
        for needle in ("getTime()+9", "CF_TZ", "kstParts", "getHours()", "timeZone"):
            print(needle, needle in f)
        i = f.find("function tick")
        print(f[i : i + 650])
