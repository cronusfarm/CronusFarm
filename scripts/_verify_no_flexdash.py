#!/usr/bin/env python3
import json
from pathlib import Path

d = json.loads(Path("/home/dooly/.node-red/flows.json").read_text(encoding="utf-8"))
n = [
    x
    for x in d
    if isinstance(x, dict)
    and (
        "flexdash" in (x.get("type") or "").lower()
        or x.get("z") == "tab_cronus_flexdash"
        or (x.get("id") or "").startswith("fd_toggle_")
    )
]
print("flexdash_nodes", len(n))
print("total_nodes", len(d))
