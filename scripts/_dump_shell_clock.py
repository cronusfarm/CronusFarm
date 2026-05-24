#!/usr/bin/env python3
import json
from pathlib import Path

for label, path in [
    ("local", Path(__file__).resolve().parents[1] / "nodered/merged-deploy.json"),
    ("pi", Path("/home/dooly/.node-red/flows.json")),
]:
    if not path.is_file():
        continue
    d = json.loads(path.read_text(encoding="utf-8"))
    for n in d:
        if n.get("id") != "ui_tpl_shell_html":
            continue
        f = n["format"]
        print(f"=== {label} ui_tpl_shell_html ===")
        i = f.find('id="clock"')
        print(f[i - 60 : i + 180] if i >= 0 else "no clock id")
        j = f.find("var CF_TZ")
        print(f[j : j + 950] if j >= 0 else "no CF_TZ")
        k = f.find("getTime()+9")
        print("getTime()+9 at", k)
