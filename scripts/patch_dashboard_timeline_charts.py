# -*- coding: utf-8 -*-
"""대시보드 히스토그램: anchor_ts_ms 기준 x축 + combo loadCh 구조 정리, maintainAspectRatio true."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

OLD_T0 = "const t0 = pts.length ? pts[0].ts_ms : Date.now();"
NEW_T0 = (
    "const t0 = (j.anchor_ts_ms != null && j.anchor_ts_ms !== undefined) "
    "? j.anchor_ts_ms : (pts.length ? pts[0].ts_ms : Date.now());"
)

OLD_LOADCH = """  async function loadCh(ch) {
    const u = API + '?device_id=' + encodeURIComponent(deviceId()) + '&channel=' + encodeURIComponent(ch) + '&hours=24';
    const r = await fetch(u, { credentials: 'same-origin' });
    if (!r.ok) return [];
    const j = await r.json();
    return j.points || [];
  }
  async function load() {
    const el = document.getElementById('cfhc_combo_a');
    if (!el) return;
    try {
      const all = [];
      for (const ch of CHANNELS) all.push(await loadCh(ch));
      let t0 = Date.now() - 86400000;
      for (const pts of all) { if (pts.length && pts[0].ts_ms < t0) t0 = pts[0].ts_ms; }
      const datasets = CHANNELS.map(function(ch, i) {
        const pts = all[i];"""

NEW_LOADCH_A = """  async function loadCh(ch) {
    const u = API + '?device_id=' + encodeURIComponent(deviceId()) + '&channel=' + encodeURIComponent(ch) + '&hours=24';
    const r = await fetch(u, { credentials: 'same-origin' });
    if (!r.ok) return { points: [], anchor_ts_ms: null };
    const j = await r.json();
    return { points: j.points || [], anchor_ts_ms: j.anchor_ts_ms };
  }
  async function load() {
    const el = document.getElementById('cfhc_combo_a');
    if (!el) return;
    try {
      const all = [];
      for (const ch of CHANNELS) all.push(await loadCh(ch));
      let t0 = null;
      for (let k = 0; k < all.length; k++) {
        const a = all[k].anchor_ts_ms;
        if (a != null) { t0 = a; break; }
      }
      if (t0 == null) {
        t0 = Date.now() - 86400000;
        for (let k = 0; k < all.length; k++) {
          const pts = all[k].points;
          if (pts.length && (t0 == null || pts[0].ts_ms < t0)) t0 = pts[0].ts_ms;
        }
      }
      const datasets = CHANNELS.map(function(ch, i) {
        const pts = all[i].points;"""

NEW_LOADCH_B = NEW_LOADCH_A.replace("cfhc_combo_a", "cfhc_combo_b")


def main() -> None:
    d = json.loads(DASH.read_text(encoding="utf-8-sig"))
    nchg = 0
    for n in d:
        if n.get("type") != "ui_template":
            continue
        fmt = n.get("format") or ""
        if OLD_T0 not in fmt:
            continue
        fmt = fmt.replace(OLD_T0, NEW_T0, 1)
        nid = n.get("id") or ""
        if nid == "ui_tpl_hist_combo_a" and OLD_LOADCH in fmt:
            fmt = fmt.replace(OLD_LOADCH, NEW_LOADCH_A, 1)
        if nid == "ui_tpl_hist_combo_b" and OLD_LOADCH in fmt:
            fmt = fmt.replace(OLD_LOADCH, NEW_LOADCH_B, 1)
        if "maintainAspectRatio: false" in fmt:
            fmt = fmt.replace("maintainAspectRatio: false", "maintainAspectRatio: true", 1)
            nchg += 1
        n["format"] = fmt
        nchg += 1
    DASH.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("OK dashboard timeline patches, nodes_touched=", nchg)


if __name__ == "__main__":
    main()
