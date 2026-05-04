"""
flows_cronusfarm_dashboard.json 의 내용(포맷·함수·그룹·wires 등)을
CronusFarm_NodeRED_flow.json 에 합치되, 편집기 좌표(x,y,z)만 내보내기 쪽을 유지합니다.

분할 파일에 있는 모든 노드(id 일치)를 병합합니다.
분할에서 빠진 대시보드 탭(tab_cronus_dash) 노드는 내보내기에서 삭제합니다.

사용: python scripts/sync_nodered_dashboard_into_export.py
"""
import json
from pathlib import Path

EXPORT = "CronusFarm_NodeRED_flow.json"
DASH = "flows_cronusfarm_dashboard.json"

# x,y,z만 내보내기(편집기) 유지. wires는 flows_cronusfarm_dashboard.json이 우선(배선 수정이 배포에 반영되게).
PRESERVE = frozenset({"x", "y", "z"})


def sync_dashboard_into_export(nodered_dir: Path | None = None) -> tuple[int, int, int]:
    """내보내기 파일을 갱신하고, (병합 수, 신규 추가 수, 대시보드 탭에서 삭제된 노드 제거 수)를 반환합니다."""
    root = nodered_dir or Path(__file__).resolve().parents[1] / "nodered"
    exp_p = root / EXPORT
    dash_p = root / DASH
    if not exp_p.is_file() or not dash_p.is_file():
        raise FileNotFoundError(f"필요 파일: {exp_p} , {dash_p}")
    mono: list = json.loads(exp_p.read_text(encoding="utf-8-sig"))
    dash: list = json.loads(dash_p.read_text(encoding="utf-8-sig"))
    dmap = {
        n["id"]: n
        for n in dash
        if isinstance(n, dict) and n.get("id") is not None
    }
    merged_count = 0
    for i, n in enumerate(mono):
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        if nid not in dmap:
            continue
        src = dmap[nid]
        merged = dict(src)
        for k in PRESERVE:
            if k in n:
                merged[k] = n[k]
        mono[i] = merged
        merged_count += 1

    mono_ids = {
        n.get("id")
        for n in mono
        if isinstance(n, dict) and n.get("id") is not None
    }
    appended = 0
    for n in dash:
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        if not nid or nid in mono_ids:
            continue
        mono.append(dict(n))
        mono_ids.add(nid)
        appended += 1

    # 분할 dashboard 에서 삭제된 노드가 내보내기에 남지 않도록 제거(tab_cronus_dash 만)
    dash_tab_z = "tab_cronus_dash"
    before_prune = len(mono)
    mono = [
        n
        for n in mono
        if not (
            isinstance(n, dict)
            and n.get("z") == dash_tab_z
            and n.get("id") not in dmap
        )
    ]
    pruned = before_prune - len(mono)

    exp_p.write_text(json.dumps(mono, ensure_ascii=False), encoding="utf-8")
    return merged_count, appended, pruned


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "nodered"
    try:
        m, a, pruned = sync_dashboard_into_export(root)
    except FileNotFoundError as e:
        raise SystemExit(str(e))
    extra = f", 신규 추가 {a}개" if a else ""
    pr_msg = f", 대시보드 탭 정리 {pruned}개" if pruned else ""
    print(f"OK {EXPORT} <- dashboard 필드 병합 (좌표 유지) 노드 {m}개{extra}{pr_msg}")


if __name__ == "__main__":
    main()
