#!/bin/bash
# Pi에서 실행: Node-RED 최신/구버전(v0.5.1) 경로 분리 제공
#
# 목표(외부 접속, 포트 1880 기준)
# - 최신 작업: /admin , /ui  (기존 방식 유지)
# - 구버전 보기 전용: /admin/v0.5 , /ui/0.5
#
# 구현
# - nginx(1880): 경로별 프록시
# - node-red 최신: 1882로 이동
# - node-red v0.5.1: 1881로 추가 인스턴스 실행(별도 userDir)
#
# 주의
# - 이 스크립트는 systemd 설정을 변경하고 서비스를 재시작합니다.
# - 관리자 권한(sudo)이 필요합니다.

set -euo pipefail

echo "[1/6] 필수 패키지 설치(nginx)"
if ! command -v nginx >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y nginx
fi

echo "[2/6] Node-RED 최신 인스턴스(기존 nodered.service) 포트 이동: 1880 -> 1882"
sudo mkdir -p /etc/systemd/system/nodered.service.d
sudo tee /etc/systemd/system/nodered.service.d/cronusfarm-port.conf >/dev/null <<'EOF'
[Service]
Environment=PORT=1882
EOF

echo "[2.5/6] Node-RED 최신 설정: /admin , /ui 복구(기존 방식 유지)"
python3 - <<'PY'
import re
from pathlib import Path

settings = Path.home() / ".node-red" / "settings.js"
src = settings.read_text(encoding="utf-8", errors="replace")

def set_prop(js: str, key: str, value_js: str) -> str:
    pat = re.compile(rf"(^\s*)(//\s*)?({re.escape(key)}\s*:\s*)([^,\n]+)(\s*,?)\s*$", re.M)
    m = pat.search(js)
    if m:
        indent = m.group(1)
        return pat.sub(rf"{indent}{key}: {value_js},", js, count=1)
    return js

out = src
out = set_prop(out, "httpAdminRoot", "'/admin'")
out = set_prop(out, "httpNodeRoot", "'/'")

ui_block = re.search(r"(^\s*)ui\s*:\s*\{([\s\S]*?)\n\s*\}\s*,?", out, re.M)
if ui_block:
    block = ui_block.group(0)
    block2 = re.sub(r"(\bpath\s*:\s*)(['\"]).*?\2", r"\1'ui'", block)
    if block2 == block:
        block2 = re.sub(r"(ui\s*:\s*\{\s*\n)", r"\1        path: 'ui',\n", block, count=1)
    out = out.replace(block, block2)

if out != src:
    settings.write_text(out, encoding="utf-8")
    print("patched latest settings.js")
else:
    print("latest settings.js already ok")
PY

echo "[3/6] Node-RED v0.5.1 인스턴스 userDir 준비(~/.node-red-v05)"
V05_DIR="${HOME}/.node-red-v05"
mkdir -p "${V05_DIR}"

if [[ ! -f "${V05_DIR}/settings.js" ]]; then
  # 기존 settings.js를 기반으로 복사 후 핵심만 수정
  cp "${HOME}/.node-red/settings.js" "${V05_DIR}/settings.js"
fi

python3 - <<'PY'
import re
from pathlib import Path

udir = Path.home() / ".node-red-v05"
settings = udir / "settings.js"
src = settings.read_text(encoding="utf-8", errors="replace")

def set_prop(js: str, key: str, value_js: str) -> str:
    pat = re.compile(rf"(^\s*)(//\s*)?({re.escape(key)}\s*:\s*)([^,\n]+)(\s*,?)\s*$", re.M)
    m = pat.search(js)
    if m:
        indent = m.group(1)
        return pat.sub(rf"{indent}{key}: {value_js},", js, count=1)
    return js

out = src
out = set_prop(out, "uiPort", "1881")
out = set_prop(out, "httpAdminRoot", "'/admin/v0.5'")
out = set_prop(out, "httpNodeRoot", "'/'")

# dashboard path는 /ui/0.5 로
ui_block = re.search(r"(^\s*)ui\s*:\s*\{([\s\S]*?)\n\s*\}\s*,?", out, re.M)
if ui_block:
    block = ui_block.group(0)
    block2 = re.sub(r"(\bpath\s*:\s*)(['\"]).*?\2", r"\1'ui/0.5'", block)
    if block2 == block:
        block2 = re.sub(r"(ui\s*:\s*\{\s*\n)", r"\1        path: 'ui/0.5',\n", block, count=1)
    out = out.replace(block, block2)
else:
    ins = "\n    // CronusFarm: Dashboard(UI) v0.5 경로\n    ui: { path: 'ui/0.5' },\n"
    m = re.search(r"(^\s*uiPort\s*:\s*.*?[,]\s*$)", out, re.M)
    if m:
        out = out[: m.end()] + ins + out[m.end():]
    else:
        out = re.sub(r"(module\.exports\s*=\s*\{\s*\n)", r"\1" + ins, out, count=1)

if out != src:
    settings.write_text(out, encoding="utf-8")
    print("patched v05 settings.js")
else:
    print("v05 settings.js already ok")
PY

echo "[4/6] Node-RED v0.5.1 flows.json 반영"
if [[ -f "${V05_DIR}/flows.json" ]]; then
  cp "${V05_DIR}/flows.json" "${V05_DIR}/flows.v05.backup.$(date +%s).json"
fi
if [[ ! -f "${V05_DIR}/merged-v05.json" ]]; then
  echo "merged-v05.json 없음: ${V05_DIR}/merged-v05.json" >&2
  echo "먼저 v0.5.1 스냅샷 merged-v05.json을 해당 경로에 올려주세요." >&2
  exit 1
fi
cp "${V05_DIR}/merged-v05.json" "${V05_DIR}/flows.json"

echo "[5/6] systemd: nodered-v05.service 생성/재시작"
sudo tee /etc/systemd/system/nodered-v05.service >/dev/null <<EOF
[Unit]
Description=Node-RED (CronusFarm v0.5.1 snapshot)
After=network.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${HOME}
Environment=NODE_RED_OPTIONS=
ExecStart=/usr/bin/env node-red -u ${V05_DIR}
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now nodered-v05.service

echo "[6/6] nginx: 1880에서 경로별 프록시 구성"
sudo tee /etc/nginx/sites-available/cronusfarm-nodered.conf >/dev/null <<'EOF'
map $http_upgrade $connection_upgrade {
  default upgrade;
  ''      close;
}

server {
  listen 1880;
  server_name _;

  # 최신 Node-RED (1882) - 기본 경로(/admin, /ui)
  location / {
    proxy_pass http://127.0.0.1:1882;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }

  # 구버전 Editor/Admin: /admin/v0.5 -> 1881
  location ^~ /admin/v0.5/ {
    proxy_pass http://127.0.0.1:1881/admin/v0.5/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
  }
  location = /admin/v0.5 {
    return 301 /admin/v0.5/;
  }

  # 구버전 Dashboard(UI): /ui/0.5 -> 1881
  location ^~ /ui/0.5/ {
    proxy_pass http://127.0.0.1:1881/ui/0.5/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
  }
  location = /ui/0.5 {
    return 301 /ui/0.5/;
  }
}
EOF

sudo ln -sf /etc/nginx/sites-available/cronusfarm-nodered.conf /etc/nginx/sites-enabled/cronusfarm-nodered.conf
sudo nginx -t
sudo systemctl restart nginx

echo "OK: nginx(1880) + node-red(latest=1882) + node-red(v0.5=1881) 구성 완료"

