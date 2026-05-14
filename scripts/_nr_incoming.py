import json
import sys

path, target = sys.argv[1], sys.argv[2]
d = json.loads(open(path, encoding="utf-8").read())
for n in d:
    for w in n.get("wires") or []:
        if target in w:
            print("FROM", n.get("id"), n.get("type"), n.get("name"))
