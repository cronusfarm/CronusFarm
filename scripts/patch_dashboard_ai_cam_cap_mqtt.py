#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""대시보드 AI 캡션: MQTT JSON 전체를 ui_template에 전달(로딩 고착 방지)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
EXPORT = ROOT / "nodered" / "CronusFarm_NodeRED_flow.json"

NEW_FUNC = r"""let cap = '실시간 온실 영상 (캡션 대기)';
let out = { caption: cap, count: 0, crop_name: '—', crop_count: 0, leaf_count: 0 };
try {
  let o = msg.payload;
  if (typeof o === 'string') {
    try { o = JSON.parse(o); } catch (e2) { o = null; }
  }
  if (o && typeof o === 'object' && !Array.isArray(o)) {
    const cn = o.crop_name != null ? String(o.crop_name) : '—';
    const cc = o.crop_count != null ? Number(o.crop_count) : 0;
    const lc = o.leaf_count != null ? Number(o.leaf_count) : (typeof o.count === 'number' ? o.count : 0);
    let c = (o.caption && String(o.caption).trim()) || '';
    if (!c && cn !== '—') c = '작물: ' + cn + ' | 개수: ' + cc + ' | 잎: ' + lc;
    if (!c && typeof o.count === 'number') c = '검출 ' + o.count + '개';
    const src = o.source != null ? String(o.source) : '';
    if (src && /gemini|manual_|^cache$/.test(src) && c.indexOf('(AI추정)') < 0) {
      c = c + ' (AI추정)';
    }
    out = {
      count: typeof o.count === 'number' ? o.count : lc,
      caption: c || cap,
      crop_name: cn,
      crop_count: cc,
      leaf_count: lc,
    };
  }
} catch (e) {}
msg.payload = out;
return msg;"""

OLD_SNIP = "msg.payload = cap;\nreturn msg;"


def patch_file(path: Path) -> bool:
    if not path.is_file():
        return False
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    changed = False
    for n in data:
        if not isinstance(n, dict):
            continue
        if n.get("id") == "fn_cf_ai_cam_cap":
            if OLD_SNIP in (n.get("func") or ""):
                n["func"] = NEW_FUNC
                changed = True
        if n.get("id") == "nr_node_ui_ai_stream" and isinstance(n.get("format"), str):
            n["format"] = n["format"].replace(
                "실시간 온실 영상 (로딩)", "실시간 온실 영상 (캡션 대기)"
            ).replace(
                "실시간 온실 영상 (캡션 로딩)", "실시간 온실 영상 (캡션 대기)"
            )
            changed = True
    if changed:
        path.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    return changed


def main() -> None:
    ok = False
    if patch_file(DASH):
        print("OK", DASH)
        ok = True
    if patch_file(EXPORT):
        print("OK", EXPORT)
        ok = True
    if not ok:
        raise SystemExit("fn_cf_ai_cam_cap not patched")


if __name__ == "__main__":
    main()
