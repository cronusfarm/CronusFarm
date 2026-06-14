#!/usr/bin/env python3
import json
from pathlib import Path

d = json.loads(Path("/home/dooly/.node-red/flows.json").read_text(encoding="utf-8"))
for n in d:
    f = n.get("format") or ""
    func = n.get("func") or ""
    blob = f + func
    if "getTime()+9" in blob or "getTime() + 9" in blob:
        print("OLD+9", n.get("id"), n.get("name"), n.get("type"))
    if "#clock" in f or "cf-monitor-tab-clock" in f:
        print("CLOCK_NODE", n.get("id"), n.get("name"), n.get("type"),
              "CF_TZ" in f, "timeZone" in f, "getTime()+9" in f)
