#!/usr/bin/env python3
"""Pi flows.json — 모니터 템플릿 숨김 여부 빠른 점검."""
from __future__ import annotations

import json
import sys
from pathlib import Path

flows = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/home/dooly/.node-red/flows.json")
raw = json.loads(flows.read_text(encoding="utf-8-sig"))
stub = "cf-dev-merged-hidden"
ai = next((n for n in raw if n.get("id") == "nr_node_ui_ai_stream"), None)
fmt = (ai or {}).get("format") or ""
print("nodered:", "active" if flows.is_file() else "missing")
print("ai_stream len:", len(fmt), "hidden:", stub in fmt)
beds = [
    n
    for n in raw
    if n.get("type") == "ui_template"
    and "Bed" in (n.get("name") or "")
    and "타임" in (n.get("name") or "")
]
print("bed timeline tpl:", len(beds))
for b in beds[:4]:
    f = b.get("format") or ""
    print(" ", b.get("name"), "len", len(f), "hidden", stub in f)
hidden = [
    n
    for n in raw
    if n.get("type") == "ui_template" and stub in (n.get("format") or "")
]
print("hidden ui_template total:", len(hidden))
for n in hidden[:8]:
    print(" ", n.get("id"), n.get("name"))
