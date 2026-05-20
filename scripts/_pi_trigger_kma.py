#!/usr/bin/env python3
import json

p = "/home/dooly/.node-red/flows.json"
flows = json.load(open(p, encoding="utf-8"))
for n in flows:
    if not isinstance(n, dict):
        continue
    name = str(n.get("name", ""))
    if n.get("type") == "inject" and "KMA" in name:
        print(n["id"], name, n.get("crontab", ""))
