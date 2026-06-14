#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import sys

p = sys.argv[1] if len(sys.argv) > 1 else "/home/dooly/.node-red/flows.json"
d = json.load(open(p, encoding="utf-8"))
for nid in (
    "mqtt_in_kma_snap",
    "inj_farm_env_merge",
    "ui_tpl_farm_env",
    "cf_fn_kma_cache",
):
    n = next((x for x in d if isinstance(x, dict) and x.get("id") == nid), None)
    if not n:
        print(nid, "MISSING")
        continue
    print(
        nid,
        "disabled=",
        n.get("disabled"),
        "z=",
        n.get("z"),
        "wires=",
        n.get("wires"),
    )
    if nid == "mqtt_in_kma_snap":
        print("  topic=", n.get("topic"), "broker=", n.get("broker"))
