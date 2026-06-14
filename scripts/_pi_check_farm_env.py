#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pi flows.json Farm 환경 노드 점검."""
import json
import sys

p = sys.argv[1] if len(sys.argv) > 1 else "/home/dooly/.node-red/flows.json"
d = json.load(open(p, encoding="utf-8"))
ids = {n.get("id") for n in d if isinstance(n, dict)}
need = [
    "ui_tpl_farm_env",
    "cf_fn_farm_env_merge",
    "cf_fn_kma_cache",
    "mqtt_in_kma_snap",
    "inj_farm_env_merge",
    "ui_grp_farm",
]
for nid in need:
    n = next((x for x in d if isinstance(x, dict) and x.get("id") == nid), None)
    print(nid, "OK" if n else "MISSING")
    if not n:
        continue
    if nid == "ui_tpl_farm_env":
        f = n.get("format") or ""
        print(
            "  h=%s grp=%s kma=%s len=%s"
            % (n.get("height"), n.get("group"), "기상청 KMA" in f, len(f))
        )
    elif nid in ("mqtt_in_kma_snap", "cf_fn_farm_env_merge", "cf_fn_kma_cache"):
        print("  wires=", n.get("wires"))
