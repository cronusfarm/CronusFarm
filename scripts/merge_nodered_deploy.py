"""
nodered/merged-deploy.json 생성.
- 기본: CronusFarm_NodeRED_flow.json 이 있으면, 먼저 flows_cronusfarm_dashboard.json → 내보내기 동기화(좌표 유지) 후 복사.
- --use-split: 분할 3파일만 이어붙임(동기화·내보내기 미사용).
- --from-export: 내보내기만 → merged(동기화는 옵션과 같음).
- --no-sync: dashboard → 내보내기 병합 생략.
"""

import json

import subprocess
import sys

from pathlib import Path



EXPORT_NAME = "CronusFarm_NodeRED_flow.json"





def maybe_sync_dashboard_export(root: Path) -> None:
    """분할 dashboard 를 내보내기에 반영(좌표 유지). --no-sync 이면 생략."""
    if "--no-sync" in sys.argv:
        return
    mono = root / "nodered" / EXPORT_NAME
    dash = root / "nodered" / "flows_cronusfarm_dashboard.json"
    sync_py = root / "scripts" / "sync_nodered_dashboard_into_export.py"
    if not mono.is_file() or not dash.is_file() or not sync_py.is_file():
        return
    r = subprocess.run(
        [sys.executable, str(sync_py)],
        cwd=str(root),
    )
    if r.returncode != 0:
        raise SystemExit("sync_nodered_dashboard_into_export.py 실패")





def main() -> None:

    root = Path(__file__).resolve().parents[1]

    out_path = root / "nodered" / "merged-deploy.json"

    mono = root / "nodered" / EXPORT_NAME



    paths = [

        root / "nodered" / "flows_cronusfarm_mqtt.json",

        root / "nodered" / "flows_cronusfarm_dashboard.json",

        root / "nodered" / "flows_cronusfarm_devflow_flow.json",

    ]



    def write_split() -> int:

        out: list[object] = []

        for p in paths:

            out.extend(json.loads(p.read_text(encoding="utf-8-sig")))

        out_path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")

        return len(out)



    # 명시: 분할 JSON만 사용(CI·위치 무관)

    if "--use-split" in sys.argv:

        n = write_split()

        print(f"OK merged-deploy.json <- 분할 3파일 nodes={n}")

        return



    # 명시: 내보내기만 (파일 필수)

    if "--from-export" in sys.argv:

        maybe_sync_dashboard_export(root)

        if not mono.is_file():

            raise SystemExit(f"없음: {mono}")

        data = json.loads(mono.read_text(encoding="utf-8-sig"))

        if not isinstance(data, list):

            raise SystemExit(f"JSON 최상위는 배열이어야 함: {mono}")

        out_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        print(f"OK merged-deploy.json <- {EXPORT_NAME} nodes={len(data)}")

        return



    # 기본: 편집기 좌표 유지 — 내보내기 파일이 있으면 그걸 사용

    if mono.is_file():

        maybe_sync_dashboard_export(root)

        data = json.loads(mono.read_text(encoding="utf-8-sig"))

        if not isinstance(data, list):

            raise SystemExit(f"JSON 최상위는 배열이어야 함: {mono}")

        out_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        print(f"OK merged-deploy.json <- {EXPORT_NAME} (기본, 노드 위치 유지) nodes={len(data)}")

        return



    n = write_split()

    print(f"OK merged-deploy.json <- 분할 3파일 (내보내기 없음) nodes={n}")





if __name__ == "__main__":

    main()


