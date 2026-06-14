#!/usr/bin/env python3
import json
from pathlib import Path

d = json.loads(Path("/home/dooly/.node-red/flows.json").read_text(encoding="utf-8"))
for n in d:
    f = n.get("format") or ""
    if "cf-shell" not in f and "cf-monitor-tab-clock" not in f:
        continue
    print(
        n.get("id"),
        n.get("name"),
        "shell" if "cf-shell" in f else "",
        "toolbar" if "cf-monitor-tab-clock" in f else "",
        "CF_TZ" in f,
        "timeZone:Asia" in f.replace(" ", ""),
        "getTime()+9" in f,
        "toLocaleString" in f,
    )
