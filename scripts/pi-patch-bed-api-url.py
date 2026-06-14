#!/usr/bin/env python3
"""Pi에서 ~/.node-red/flows.json 의 Bed API POST URL을 /api/cronus/bed 로 수정."""
import json
import pathlib

p = pathlib.Path.home() / ".node-red" / "flows.json"
j = json.loads(p.read_text(encoding="utf-8"))
for n in j:
    if n.get("id") == "http_in_beds_post":
        n["url"] = "/api/cronus/bed"
        n["name"] = "POST /api/cronus/bed"
    if n.get("id") == "tab_cronus_bedapi":
        n["info"] = (
            "SQLite ~/CronusFarm/data/cronusfarm.sqlite\n"
            "- GET /api/cronus/beds\n"
            "- POST /api/cronus/bed\n"
            "시드: scripts/pi-seed-cronusfarm-environment.sh"
        )
p.write_text(json.dumps(j, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print("patched", p)
