#!/usr/bin/env python3
import json
import sys

p = sys.argv[1] if len(sys.argv) > 1 else "/home/dooly/.node-red/flows.json"
with open(p, encoding="utf-8") as f:
    flows = json.load(f)
for n in flows:
    if not isinstance(n, dict):
        continue
    name = str(n.get("name", ""))
    nid = str(n.get("id", ""))
    if "tg_news" in nid or "09:00" in name or "17:00" in name or "텔레그램 뉴스" in name:
        print(nid, n.get("type"), name, n.get("crontab", ""))
