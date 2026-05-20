# -*- coding: utf-8 -*-
"""Bed 타임라인: 채널 API 병렬 로드 + Chart.js 전역 1회 로드 (느린 순차 await 제거)."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

OLD_LOADALL = re.compile(
    r"async function loadAll\(\) \{\s*"
    r"for \(let i = 0; i < CHANNELS\.length; i\+\+\) await loadOne\(i\);\s*"
    r"\}",
    re.MULTILINE,
)
NEW_LOADALL = (
    "async function loadAll() {\n"
    "    await Promise.all(CHANNELS.map(function(_, i) { return loadOne(i); }));\n"
    "  }"
)

OLD_ENSURE = re.compile(
    r"function ensureChart\(cb\) \{\s*"
    r"if \(typeof Chart !== 'undefined'\) \{ cb\(\); return; \}\s*"
    r"var s = document\.querySelector\('script\[src\*=\"chart\.umd\"\]'\);\s*"
    r"if \(s && !s\.getAttribute\('data-cf-fail'\)\) \{\s*"
    r"setTimeout\(function\(\) \{ ensureChart\(cb\); \}, 150\);\s*"
    r"return;\s*"
    r"\}\s*"
    r"s = document\.createElement\('script'\);\s*"
    r"s\.src = '/cronusfarm-static/vendor/chart\.umd\.min\.js';\s*"
    r"s\.onload = cb;\s*"
    r"s\.onerror = function\(\) \{\s*"
    r"s\.setAttribute\('data-cf-fail', '1'\);\s*"
    r"var cdn = document\.createElement\('script'\);\s*"
    r"cdn\.src = 'https://cdn\.jsdelivr\.net/npm/chart\.js@4\.4\.1/dist/chart\.umd\.min\.js';\s*"
    r"cdn\.onload = cb;\s*"
    r"document\.head\.appendChild\(cdn\);\s*"
    r"\};\s*"
    r"document\.head\.appendChild\(s\);\s*"
    r"\}",
    re.MULTILINE,
)

NEW_ENSURE = """function ensureChart(cb) {
    if (typeof Chart !== 'undefined') { cb(); return; }
    var g = window.__cfChartJsReady;
    if (!g) {
      g = new Promise(function(resolve, reject) {
        function ok() { resolve(); }
        var s = document.querySelector('script[src*="chart.umd"]');
        if (!s) {
          s = document.createElement('script');
          s.src = '/cronusfarm-static/vendor/chart.umd.min.js';
          s.onload = ok;
          s.onerror = function() {
            var cdn = document.createElement('script');
            cdn.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js';
            cdn.onload = ok;
            cdn.onerror = function() { reject(new Error('chart.js load failed')); };
            document.head.appendChild(cdn);
          };
          document.head.appendChild(s);
          return;
        }
        var n = 0;
        (function wait() {
          if (typeof Chart !== 'undefined') { ok(); return; }
          if (++n > 50) { reject(new Error('chart.js timeout')); return; }
          setTimeout(wait, 40);
        })();
      });
      window.__cfChartJsReady = g;
    }
    g.then(cb).catch(function(e) { console.warn(e); });
  }"""


def main() -> None:
    data = json.loads(DASH.read_text(encoding="utf-8-sig"))
    n = 0
    for node in data:
        nid = node.get("id") or ""
        if not str(nid).startswith("ui_tpl_hist_stack_"):
            continue
        fmt = node.get("format") or ""
        orig = fmt
        fmt = OLD_LOADALL.sub(NEW_LOADALL, fmt)
        fmt = OLD_ENSURE.sub(NEW_ENSURE, fmt, count=1)
        fmt = fmt.replace("ensureChart(loadAll); }}, 700);", "ensureChart(loadAll); }}, 80);")
        if fmt != orig:
            node["format"] = fmt
            n += 1
    if not n:
        raise SystemExit("ui_tpl_hist_stack_* 에 패치할 대상 없음(이미 적용됨?)")
    DASH.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"OK parallel timeline load: {n} bed template(s)")


if __name__ == "__main__":
    main()
