#!/usr/bin/env python3
"""Node-RED: flow context → cmd 일괄 재생(parts.join) 노드 비활성화 — tele OFF 시 수동 고정 방지."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOWS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
MARK = "parts.join"


def main() -> int:
    if not FLOWS.is_file():
        print(f"skip: {FLOWS} not found", file=sys.stderr)
        return 1
    nodes = json.loads(FLOWS.read_text(encoding="utf-8"))
    n = 0
    for node in nodes:
        if not isinstance(node, dict):
            continue
        fn = node.get("func") or ""
        if MARK not in fn or "cronusfarm" not in fn or "/cmd" not in fn:
            continue
        if node.get("d"):
            continue
        node["d"] = True
        node["disabled"] = True
        n += 1
        print(f"disabled {node.get('id')} {node.get('name') or node.get('type')}")
    if n:
        FLOWS.write_text(
            json.dumps(nodes, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"done: disabled {n} node(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
