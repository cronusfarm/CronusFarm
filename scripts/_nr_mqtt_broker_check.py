#!/usr/bin/env python3
"""Node-RED flows.json 내 mqtt-broker 노드 출력."""
import glob
import json
import sys

paths = ["/home/dooly/.node-red/flows.json"] + glob.glob("/home/dooly/.node-red/flows_*.json")
seen = set()
for p in paths:
    try:
        data = json.load(open(p, encoding="utf-8-sig"))
    except OSError:
        continue
    for n in data:
        if not isinstance(n, dict) or n.get("type") != "mqtt-broker":
            continue
        bid = n.get("id", "")
        if bid in seen:
            continue
        seen.add(bid)
        print(
            f"{p}\t{n.get('name','')}\t{n.get('broker','')}\t{n.get('port','')}\t"
            f"clientid={n.get('clientid','')}"
        )

if not seen:
    print("no mqtt-broker nodes", file=sys.stderr)
    sys.exit(1)
