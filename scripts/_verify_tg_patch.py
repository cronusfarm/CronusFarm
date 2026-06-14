#!/usr/bin/env python3
import json
from pathlib import Path

d = json.loads(Path("/home/dooly/.node-red/flows.json").read_text(encoding="utf-8"))
for n in d:
    if n.get("id") == "cf_fn_tg_dispatch":
        f = n["func"]
        print("dispatch caption:", "m.caption" in f, "visionBusy:", "cfTgVisionBusy" in f)
    if n.get("id") == "cf_fn_tg_photo_run":
        f = n["func"]
        print("photo --question:", "--question" in f, "finally:", "finally" in f)
