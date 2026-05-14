#!/bin/bash
# Pi에서 실행: Node-RED settings.js 경로 루트 설정
# - Editor/Admin: /admin
# - Dashboard(UI): /ui
# - FlexDash: /flexdash 유지 (httpNodeRoot를 건드리지 않음)
# - HTTP API 프리픽스(/farm/cronusfarm/...)는 플로우의 http in url에서 직접 처리
#
# 사용:
#   bash pi-nodered-apply-settings-farm.sh
#
# 주의:
# - settings.js는 JS 파일이라 "정식 AST 파서" 없이 텍스트 패치로 처리합니다.
# - 기존 설정이 있으면 최대한 유지하고, 필요한 항목만 교체/삽입합니다.

set -eu

USERDIR="${HOME}/.node-red"
SETTINGS="${USERDIR}/settings.js"

if [[ ! -f "${SETTINGS}" ]]; then
  echo "settings.js 없음: ${SETTINGS}" >&2
  exit 1
fi

python3 - <<'PY'
import re
from pathlib import Path

settings = Path.home() / ".node-red" / "settings.js"
src = settings.read_text(encoding="utf-8", errors="replace")

def set_prop(js: str, key: str, value_js: str) -> str:
    # key: value, 형태가 있으면 교체
    pat = re.compile(rf"(^\s*)(//\s*)?({re.escape(key)}\s*:\s*)([^,\n]+)(\s*,?)\s*$", re.M)
    m = pat.search(js)
    if m:
        indent = m.group(1)
        comma = ","  # 항상 콤마 유지(중간 삽입 대비)
        return pat.sub(rf"{indent}{key}: {value_js}{comma}", js, count=1)
    return js

out = src
out2 = set_prop(out, "httpAdminRoot", "'/admin'")
out2 = set_prop(out2, "httpNodeRoot", "'/'")

# dashboard1(node-red-dashboard) 설정: ui: { path: "ui" }
# 1) ui 블록이 있으면 path를 ui로 강제
ui_block = re.search(r"(^\s*)ui\s*:\s*\{([\s\S]*?)\n\s*\}\s*,?", out2, re.M)
if ui_block:
    block = ui_block.group(0)
    # path: '...' or "..."
    block2 = re.sub(r"(\bpath\s*:\s*)(['\"]).*?\2", r"\1'ui'", block)
    if block2 == block:
        # path가 없으면 블록 시작 바로 뒤에 삽입
        block2 = re.sub(r"(ui\s*:\s*\{\s*\n)", r"\1        path: 'ui',\n", block, count=1)
    out2 = out2.replace(block, block2)
else:
    # 2) ui 블록이 없으면, uiPort 근처에 삽입
    ins = "\n    // CronusFarm: Dashboard(UI) 경로\n    ui: { path: 'ui' },\n"
    m = re.search(r"(^\s*uiPort\s*:\s*.*?[,]\s*$)", out2, re.M)
    if m:
        out2 = out2[: m.end()] + ins + out2[m.end():]
    else:
        # fallback: module.exports 시작 다음 줄에 삽입
        out2 = re.sub(r"(module\.exports\s*=\s*\{\s*\n)", r"\1" + ins, out2, count=1)

# httpAdminRoot가 없었으면 같은 방식으로 삽입
def ensure_inserted(js: str, key: str, value_js: str) -> str:
    if re.search(rf"\b{re.escape(key)}\s*:", js):
        return js
    ins = f"    // CronusFarm: 경로 루트\n    {key}: {value_js},\n"
    m = re.search(r"(^\s*uiPort\s*:\s*.*?[,]\s*$)", js, re.M)
    if m:
        return js[: m.end()] + ins + js[m.end():]
    return re.sub(r"(module\.exports\s*=\s*\{\s*\n)", r"\1" + ins, js, count=1)

out2 = ensure_inserted(out2, "httpAdminRoot", "'/admin'")

# CronusFarm 정적 HTML: /cronusfarm-static/<파일명> → ~/CronusFarm/nodered/dashboard
def ensure_http_static(js: str) -> str:
    home = str(Path.home()).replace("\\", "/")
    root = home + "/CronusFarm/nodered/dashboard"
    # 잘못된 삽입 복구: //httpStatic: [ 주석인데 그 다음 줄에 객체만 있는 경우(구문 오류)
    js = re.sub(
        r"(^\s*//httpStatic:\s*\[\s*)\n\s*\{path:\s*['\"]/cronusfarm-static['\"]\s*,\s*root:\s*['\"][^'\"]*['\"]\s*\},\s*\n",
        r"\1\n",
        js,
        flags=re.M,
    )
    # 기존 항목의 root만 교체(이미 httpStatic이 있어도 경로 갱신)
    m = re.search(
        r"(path\s*:\s*['\"]/cronusfarm-static['\"]\s*,\s*root\s*:\s*['\"])([^'\"]*)(['\"])",
        js,
    )
    if m:
        return js[: m.start(2)] + root + js[m.end(2) :]
    if re.search(r"(?m)^\s*httpStatic\s*:", js):
        m2 = re.search(r"(?m)^\s*httpStatic\s*:\s*\[", js)
        if m2 and "/cronusfarm-static" not in js[m2.start() : m2.start() + 800]:
            ins = m2.end()
            entry = f"\n        {{path: '/cronusfarm-static', root: '{root}'}},\n"
            return js[:ins] + entry + js[ins:]
        return js
    cctv_root = home + "/CronusFarm/CCTV"
    block = (
        "    // CronusFarm: dashboard HTML + CCTV 스냅샷(/cctv/...)\n"
        "    httpStatic: [\n"
        f"        {{path: '/cronusfarm-static', root: '{root}'}},\n"
        f"        {{path: '/cctv', root: '{cctv_root}'}}\n"
        "    ],\n"
    )
    m3 = re.search(r"(^\s*uiPort\s*:\s*.*?[,]\s*$)", js, re.M)
    if m3:
        return js[: m3.end()] + "\n" + block + js[m3.end():]
    return re.sub(r"(module\.exports\s*=\s*\{\s*\n)", r"\1" + block, js, count=1)


# CCTV 스냅샷: Grafana/브라우저에서 /cctv/cam01/latest.jpg (scripts/cronusfarm_cctv_capture_daemon.py 출력과 동일 경로)
def ensure_cctv_http_static(js: str) -> str:
    home = str(Path.home()).replace("\\", "/")
    cctv_root = home + "/CronusFarm/CCTV"
    m = re.search(
        r"(path\s*:\s*['\"]/cctv['\"]\s*,\s*root\s*:\s*['\"])([^'\"]*)(['\"])",
        js,
    )
    if m:
        return js[: m.start(2)] + cctv_root + js[m.end(2) :]
    m2 = re.search(r"(?m)^\s*httpStatic\s*:\s*\[", js)
    if not m2:
        return js
    window = js[m2.start() : m2.start() + 2500]
    if re.search(r"path\s*:\s*['\"]/cctv['\"]", window):
        return js
    ins_obj = f"\n        {{path: '/cctv', root: '{cctv_root}'}},"
    m3 = re.search(
        r"(\{\s*path\s*:\s*['\"]/cronusfarm-static['\"]\s*,\s*root\s*:\s*['\"][^'\"]+['\"]\s*\},)",
        window,
    )
    if m3:
        pos = m2.start() + m3.end(1)
        return js[:pos] + ins_obj + js[pos:]
    m4 = re.search(r"(\{\s*path\s*:\s*['\"]/cronusfarm-static['\"]\s*,\s*root\s*:\s*['\"][^'\"]+['\"]\s*\}\s*)\]", window)
    if m4:
        pos = m2.start() + m4.end(1)
        return js[:pos] + "," + ins_obj + js[pos:]
    return js


out2 = ensure_http_static(out2)
out2 = ensure_cctv_http_static(out2)

if out2 != src:
    settings.write_text(out2, encoding="utf-8")
    print("patched settings.js")
else:
    print("settings.js already ok")
PY

echo "OK: settings.js paths set"

