#!/usr/bin/env python3
"""CronusFarm FlexDash 탭·노드·모듈 의존성 제거 후 merged-deploy 재생성."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLEXDASH_TAB = "tab_cronus_flexdash"
FLEXDASH_IDS = frozenset(
    {
        "tab_cronus_flexdash",
        "fn_fd_force_manual_and_set",
        "fd_dashboard_main",
        "fd_tab_cronus",
        "fd_grid_a",
        "fd_grid_b",
    }
)


def _is_flexdash_node(node: dict) -> bool:
    if not isinstance(node, dict):
        return False
    nid = (node.get("id") or "").strip()
    typ = (node.get("type") or "").strip()
    z = (node.get("z") or "").strip()
    if nid in FLEXDASH_IDS or z == FLEXDASH_TAB:
        return True
    if typ.startswith("flexdash"):
        return True
    if typ.startswith("fd-") or typ == "fd-toggle":
        return True
    if nid.startswith("fd_toggle_"):
        return True
    return False


def _clean_wires(node: dict, removed: set[str]) -> None:
    wires = node.get("wires")
    if not isinstance(wires, list):
        return
    new_wires: list = []
    for out in wires:
        if isinstance(out, list):
            row = [t for t in out if t not in removed]
            new_wires.append(row)
        elif out not in removed:
            new_wires.append(out)
    node["wires"] = new_wires


def _strip_flexdash_modules(node: dict) -> None:
    mods = node.get("modules")
    if not isinstance(mods, dict):
        return
    for key in list(mods.keys()):
        if "flexdash" in key.lower():
            del mods[key]


def filter_flow(nodes: list) -> tuple[list, int]:
    removed_ids: set[str] = set()
    for n in nodes:
        if isinstance(n, dict) and _is_flexdash_node(n):
            rid = n.get("id")
            if rid:
                removed_ids.add(str(rid))
    if not removed_ids:
        return nodes, 0
    kept: list = []
    for n in nodes:
        if isinstance(n, dict) and _is_flexdash_node(n):
            continue
        if isinstance(n, dict):
            _clean_wires(n, removed_ids)
            _strip_flexdash_modules(n)
        kept.append(n)
    return kept, len(removed_ids)


def patch_file(path: Path) -> int:
    if not path.is_file():
        return 0
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, list):
        raise SystemExit(f"배열 아님: {path}")
    new_data, n = filter_flow(data)
    if n:
        compact = path.name in (
            "flows_cronusfarm_dashboard.json",
            "flows_cronusfarm_devflow_flow.json",
            "CronusFarm_NodeRED_flow.json",
        )
        text = (
            json.dumps(new_data, ensure_ascii=False, separators=(",", ":"))
            if compact
            else json.dumps(new_data, ensure_ascii=False, indent=2) + "\n"
        )
        path.write_text(text, encoding="utf-8")
        print(f"  {path.name}: FlexDash 노드 {n}개 제거")
    return n


def main() -> int:
    targets = [
        ROOT / "nodered" / "flows_cronusfarm_dashboard.json",
        ROOT / "nodered" / "flows_cronusfarm_devflow_flow.json",
        ROOT / "nodered" / "flows_pi_editor_latest.json",
        ROOT / "nodered" / "CronusFarm_NodeRED_flow.json",
    ]
    total = 0
    for p in targets:
        total += patch_file(p)

    merge_py = ROOT / "scripts" / "merge_nodered_deploy.py"
    if merge_py.is_file():
        r = subprocess.run(
            [sys.executable, str(merge_py), "--use-split"],
            cwd=str(ROOT),
        )
        if r.returncode != 0:
            raise SystemExit("merge_nodered_deploy.py 실패")

    print(f"OK FlexDash 제거 (총 {total}노드)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
