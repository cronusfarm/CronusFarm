import json
import sys

path = sys.argv[1]
tid = sys.argv[2]
with open(path, encoding="utf-8") as f:
    d = json.load(f)
rows = [
    (n.get("order", 0), n.get("id"), n.get("type"), n.get("name"))
    for n in d
    if n.get("type") == "ui_group" and n.get("tab") == tid
]
for r in sorted(rows, key=lambda x: (x[0], str(x[1]))):
    print(r)
