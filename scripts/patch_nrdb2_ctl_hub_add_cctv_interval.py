#!/usr/bin/env python3
"""
NRDB2 설정(/nrdb2/settings) 관제 허브에 CCTV 촬영 주기 슬라이더 추가(기존 노드 업데이트용).

- flows_cronusfarm_dashboard.json 에 이미 관제 허브 노드가 있는 경우(add 스크립트는 SKIP됨)
  -> 이 스크립트로 기존 템플릿의 rows[]에 항목을 삽입한다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

# add_nrdb2_ctl_hub_panel.py 와 동일 ID
TPL_ID = "f1e2d3c4b5a6f022"

NEW_ROW = "{ label: '사진 촬영 주기 cam01 (분)', topic: 'cctv_cam01_interval_min', min: 1, max: 720, step: 1, v: 60 }"


def _patch_format(fmt: str) -> str:
    if "cctv_cam01_interval_min" in fmt:
        return fmt

    # rows: [ ... ] 끝에 삽입(마지막 항목 뒤에 콤마가 없어도 처리)
    #
    # flows JSON에 들어간 ui-template의 format은 CRLF/공백이 다양해서
    # "rows: [" 다음부터 가장 가까운 " ]\n      ]" 같은 형태를 가정하지 않고,
    # Vue 객체 리터럴의 rows 배열만 느슨하게 매칭한다.
    m2 = re.search(r"rows:\s*\[\s*(.*?)\s*\]\s*\n\s*\]\s*\n\s*\}", fmt, flags=re.S)
    if not m2:
        m2 = re.search(r"rows:\s*\[\s*(.*?)\s*\]\s*\n\s*\}\s*\n\s*\}\s*\n\s*,?\s*\n\s*methods", fmt, flags=re.S)
    if not m2:
        m2 = re.search(r"rows:\s*\[\s*(.*?)\s*\]\s*\n\s*\}\s*\n\s*\}\s*", fmt, flags=re.S)
    if not m2:
        raise SystemExit("rows[] block not matched")

    body = m2.group(1)
    body_strip = body.rstrip()
    if not body_strip:
        new_body = "        " + NEW_ROW + "\n"
    else:
        # 마지막 줄에 콤마 보장
        if body_strip.endswith(","):
            new_body = body_strip + "\n        " + NEW_ROW + "\n"
        else:
            new_body = body_strip + ",\n        " + NEW_ROW + "\n"

    return fmt[: m2.start(1)] + new_body + fmt[m2.end(1) :]


def main() -> None:
    data = json.loads(DASH.read_text(encoding="utf-8-sig"))
    by_id = {n.get("id"): n for n in data if isinstance(n, dict)}
    n = by_id.get(TPL_ID)
    if not n:
        raise SystemExit(f"template node not found: {TPL_ID}")
    before = n.get("format", "")
    after = _patch_format(before)
    if before == after:
        print("SKIP: already patched")
        return
    n["format"] = after
    DASH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print("OK patched", DASH)


if __name__ == "__main__":
    main()

