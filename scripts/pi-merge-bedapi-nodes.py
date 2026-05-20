#!/usr/bin/env python3
"""Pi에서 /tmp/bedapi.json 의 노드를 ~/.node-red/flows.json 동일 id에 덮어쓴다."""
import json
import pathlib

flows_p = pathlib.Path.home() / ".node-red" / "flows.json"
upd = json.loads(pathlib.Path("/tmp/bedapi.json").read_text(encoding="utf-8"))
by_id = {n["id"]: n for n in upd}
fl = json.loads(flows_p.read_text(encoding="utf-8"))
ids = ("fn_beds_get", "fn_beds_post", "tab_cronus_bedapi", "http_in_beds_post")
for i, n in enumerate(fl):
    if n.get("id") in by_id and n.get("id") in ids:
        fl[i] = by_id[n["id"]]
flows_p.write_text(json.dumps(fl, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print("merged", flows_p)
