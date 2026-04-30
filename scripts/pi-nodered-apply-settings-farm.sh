#!/bin/bash
# Pi에서 실행: Node-RED settings.js 경로 루트 설정(/farm)
# - Editor/Admin: /farm
# - Dashboard(UI): /farm/ui (settings.js 의 ui.path로만 이동)
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
out2 = set_prop(out, "httpAdminRoot", "'/farm'")

# dashboard1(node-red-dashboard) 설정: ui: { path: "ui" }
# 1) ui 블록이 있으면 path를 ui로 강제
ui_block = re.search(r"(^\s*)ui\s*:\s*\{([\s\S]*?)\n\s*\}\s*,?", out2, re.M)
if ui_block:
    block = ui_block.group(0)
    # path: '...' or "..."
    block2 = re.sub(r"(\bpath\s*:\s*)(['\"]).*?\2", r"\1'farm/ui'", block)
    if block2 == block:
        # path가 없으면 블록 시작 바로 뒤에 삽입
        block2 = re.sub(r"(ui\s*:\s*\{\s*\n)", r"\1        path: 'farm/ui',\n", block, count=1)
    out2 = out2.replace(block, block2)
else:
    # 2) ui 블록이 없으면, uiPort 근처에 삽입
    ins = "\n    // CronusFarm: Dashboard(UI) 경로\n    ui: { path: 'farm/ui' },\n"
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

out2 = ensure_inserted(out2, "httpAdminRoot", "'/farm'")

if out2 != src:
    settings.write_text(out2, encoding="utf-8")
    print("patched settings.js")
else:
    print("settings.js already ok")
PY

echo "OK: settings.js paths set"

