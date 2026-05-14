import json
import sys

path, needle = sys.argv[1], sys.argv[2]
d = json.loads(open(path, encoding="utf-8").read())
for n in d:
    if needle in (n.get("func") or ""):
        print(n.get("id"), n.get("type"), n.get("name"))
