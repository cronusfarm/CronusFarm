# -*- coding: utf-8 -*-
"""Pi live flows.json — devflow iframe + HTML 재생성·적용."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOWS = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/home/dooly/.node-red/flows.json")

spec = importlib.util.spec_from_file_location("devflow_ui", ROOT / "scripts/patch_devflow_settings_ui.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

raw = json.loads(FLOWS.read_text(encoding="utf-8-sig"))
patched = mod._patch_devflow_nodes(raw)
FLOWS.write_text(json.dumps(patched, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
print(f"OK patched {FLOWS} html={mod.HTML_OUT.stat().st_size} bytes")
