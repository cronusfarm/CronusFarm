#!/usr/bin/env python3
import json
from pathlib import Path

for label, p in [
    ("flows", Path("/home/dooly/.node-red/flows.json")),
    ("index", Path("/home/dooly/.node-red/node_modules/node-red-dashboard/dist/index.html")),
]:
    t = p.read_text(encoding="utf-8")
    print(label, "V2", "__cfMonitorToolbarClockV2" in t, "syncServer", "syncServer" in t, "KST", " KST" in t)
