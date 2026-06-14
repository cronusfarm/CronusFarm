#!/usr/bin/env python3
"""tele→UI 갱신 시 MQTT cmd 재발행 방지: 스위치→cmd 함수에 tele 토픽 무시 가드 삽입."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOWS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
GUARD = (
    "\n// tele 수신으로 UI가 바뀐 경우 cmd 재발행 금지(수동 고정 루프 방지)\n"
    "if ((msg.topic || '').toString().indexOf('/tele') >= 0) return null;\n"
)
MARK = "auto_${k}=0"


def main() -> int:
    if not FLOWS.is_file():
        print(f"skip: {FLOWS}", file=sys.stderr)
        return 1
    nodes = json.loads(FLOWS.read_text(encoding="utf-8"))
    n = 0
    for node in nodes:
        if not isinstance(node, dict) or node.get("type") != "function":
            continue
        fn = node.get("func") or ""
        if MARK not in fn or GUARD.strip() in fn:
            continue
        node["func"] = GUARD + fn
        n += 1
        print(f"patched {node.get('id')} {node.get('name') or ''}")
    if n:
        FLOWS.write_text(
            json.dumps(nodes, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"done: patched {n} node(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
