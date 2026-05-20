# -*- coding: utf-8 -*-
"""Bed 타임라인: 채널별 fetch → Bed당 batch API 1회."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

OLD_API = "const API = (location.origin || '') + '/farm/cronusfarm-sqlite/api/channel/timeline';"
NEW_API = "const API_BATCH = (location.origin || '') + '/farm/cronusfarm-sqlite/api/channel/timeline/batch';"

# loadOne + per-channel fetch → renderOne + loadAll batch
OLD_BLOCK = re.compile(
    r"async function loadOne\(i\) \{\s*"
    r"const ch = CHANNELS\[i\];\s*"
    r"const el = document\.getElementById\('cf_hc_' \+ BED \+ '_' \+ ch\);\s*"
    r"if \(!el\) return;\s*"
    r"try \{\s*"
    r"const u = API \+ '\?device_id=' \+ encodeURIComponent\(deviceId\(\)\) \+ '&channel=' \+ encodeURIComponent\(ch\) \+ '&hours=24';\s*"
    r"const r = await fetch\(u, \{ credentials: 'same-origin' \}\);\s*"
    r"if \(!r\.ok\) return;\s*"
    r"const j = await r\.json\(\);\s*"
    r"const tt = mapTime\(j\);",
    re.MULTILINE,
)

NEW_START = """function renderOne(i, j) {
    const ch = CHANNELS[i];
    const el = document.getElementById('cf_hc_' + BED + '_' + ch);
    if (!el || !j) return;
    try {
      const tt = mapTime(j);"""

OLD_LOADALL = re.compile(
    r"async function loadAll\(\) \{\s*"
    r"await Promise\.all\(CHANNELS\.map\(function\(_, i\) \{ return loadOne\(i\); \}\)\);\s*"
    r"\}",
    re.MULTILINE,
)

NEW_LOADALL = """async function loadAll() {
    try {
      const u = API_BATCH + '?device_id=' + encodeURIComponent(deviceId()) + '&channels=' + encodeURIComponent(CHANNELS.join(',')) + '&hours=24';
      const r = await fetch(u, { credentials: 'same-origin' });
      if (!r.ok) return;
      const batch = await r.json();
      const map = batch.channels || {};
      await Promise.all(CHANNELS.map(function(ch, i) { return renderOne(i, map[ch]); }));
    } catch (e) { console.warn(e); }
  }"""


def main() -> None:
    data = json.loads(DASH.read_text(encoding="utf-8-sig"))
    n = 0
    for node in data:
        if not str(node.get("id", "")).startswith("ui_tpl_hist_stack_"):
            continue
        fmt = node.get("format") or ""
        orig = fmt
        fmt = fmt.replace(OLD_API, NEW_API)
        fmt = OLD_BLOCK.sub(NEW_START, fmt, count=1)
        fmt = OLD_LOADALL.sub(NEW_LOADALL, fmt, count=1)
        if fmt != orig:
            node["format"] = fmt
            n += 1
    if not n:
        raise SystemExit("패치 대상 없음(이미 batch?)")
    DASH.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"OK dashboard timeline batch: {n} bed(s)")


if __name__ == "__main__":
    main()
