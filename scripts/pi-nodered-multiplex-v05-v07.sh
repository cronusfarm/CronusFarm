#!/bin/bash
# Pi에서 실행: Node-RED 최신(작업용) + 스냅샷(v0.5/v0.7) 동시 제공
#
# 외부 접속(포트 1880 기준, nginx 프록시)
# - 작업용(최신):
#   - Editor/Admin: /admin
#   - Dashboard(UI): /ui
#   - 루트(/): /ui 로 302 리다이렉트
# - 스냅샷:
#   - v0.5: /admin/v0.5 , /ui/v0.5   (내부 ui.path는 ui05)
#   - v0.7: /admin/v0.7 , /ui/v0.7   (내부 ui.path는 ui07)
#
# 구현(내부 포트)
# - 최신 Node-RED: 1882 (기존 nodered.service PORT만 변경)
# - v0.5 스냅샷: 1881 (nodered-v05.service, userDir=~/.node-red-v05)
# - v0.7 스냅샷: 1883 (nodered-v07.service, userDir=~/.node-red-v07)
#
# 주의:
# - sudo 권한 필요
# - 스냅샷 flows 파일이 필요합니다:
#   - ~/.node-red-v05/merged-v05.json
#   - ~/.node-red-v07/merged-v07.json  (없으면 작업용 flows.json을 복사해 초기 스냅샷을 만듭니다)

set -euo pipefail

if ! sudo -n true 2>/dev/null; then
  echo "sudo 무비번 실행이 불가합니다. Pi에서 아래 명령을 직접 실행해 주세요:" >&2
  echo "  bash ~/CronusFarm/scripts/pi-nodered-multiplex-v05-v07.sh" >&2
  exit 1
fi

echo "[1/7] nginx 설치"
if ! command -v nginx >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y nginx
fi

echo "[2/7] 최신 Node-RED 포트 이동(1880 -> 1882)"
sudo mkdir -p /etc/systemd/system/nodered.service.d
sudo tee /etc/systemd/system/nodered.service.d/cronusfarm-port.conf >/dev/null <<'EOF'
[Service]
Environment=PORT=1882
EOF

echo "[2.5/7] 최신 Node-RED 경로(/admin, /ui) 설정"
python3 - <<'PY'
import re
from pathlib import Path
settings = Path.home() / ".node-red" / "settings.js"
src = settings.read_text(encoding="utf-8", errors="replace")

def set_prop(js: str, key: str, value_js: str) -> str:
    pat = re.compile(rf"(^\s*)(//\s*)?({re.escape(key)}\s*:\s*)([^,\n]+)(\s*,?)\s*$", re.M)
    if pat.search(js):
        return pat.sub(rf"\1{key}: {value_js},", js, count=1)
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

echo "[3/7] v0.5 스냅샷 userDir 준비(~/.node-red-v05)"
V05_DIR="${HOME}/.node-red-v05"
mkdir -p "${V05_DIR}"
if [[ ! -f "${V05_DIR}/settings.js" ]]; then
  cp "${HOME}/.node-red/settings.js" "${V05_DIR}/settings.js"
fi

# 스냅샷 인스턴스가 dashboard 등 동일 모듈을 쓸 수 있게 node_modules 공유
if [[ -d "${HOME}/.node-red/node_modules" ]]; then
  rm -rf "${V05_DIR}/node_modules"
  ln -s "${HOME}/.node-red/node_modules" "${V05_DIR}/node_modules"
fi

python3 - <<'PY'
import re
from pathlib import Path
udir = Path.home() / ".node-red-v05"
settings = udir / "settings.js"
src = settings.read_text(encoding="utf-8", errors="replace")

def set_prop(js: str, key: str, value_js: str) -> str:
    pat = re.compile(rf"(^\s*)(//\s*)?({re.escape(key)}\s*:\s*)([^,\n]+)(\s*,?)\s*$", re.M)
    if pat.search(js):
        return pat.sub(rf"\1{key}: {value_js},", js, count=1)
    return js

out = src
out = set_prop(out, "uiPort", "1881")
out = set_prop(out, "httpAdminRoot", "'/admin/v0.5'")
out = set_prop(out, "httpNodeRoot", "'/'")

ui_block = re.search(r"(^\s*)ui\s*:\s*\{([\s\S]*?)\n\s*\}\s*,?", out, re.M)
if ui_block:
    block = ui_block.group(0)
    block2 = re.sub(r"(\bpath\s*:\s*)(['\"]).*?\2", r"\1'ui05'", block)
    if block2 == block:
        block2 = re.sub(r"(ui\s*:\s*\{\s*\n)", r"\1        path: 'ui05',\n", block, count=1)
    out = out.replace(block, block2)

if out != src:
    settings.write_text(out, encoding="utf-8")
    print("patched v05 settings.js")
else:
    print("v05 settings.js already ok")
PY

echo "[4/7] v0.7 스냅샷 userDir 준비(~/.node-red-v07)"
V07_DIR="${HOME}/.node-red-v07"
mkdir -p "${V07_DIR}"
if [[ ! -f "${V07_DIR}/settings.js" ]]; then
  cp "${HOME}/.node-red/settings.js" "${V07_DIR}/settings.js"
fi

if [[ -d "${HOME}/.node-red/node_modules" ]]; then
  rm -rf "${V07_DIR}/node_modules"
  ln -s "${HOME}/.node-red/node_modules" "${V07_DIR}/node_modules"
fi

python3 - <<'PY'
import re
from pathlib import Path
udir = Path.home() / ".node-red-v07"
settings = udir / "settings.js"
src = settings.read_text(encoding="utf-8", errors="replace")

def set_prop(js: str, key: str, value_js: str) -> str:
    pat = re.compile(rf"(^\s*)(//\s*)?({re.escape(key)}\s*:\s*)([^,\n]+)(\s*,?)\s*$", re.M)
    if pat.search(js):
        return pat.sub(rf"\1{key}: {value_js},", js, count=1)
    return js

out = src
out = set_prop(out, "uiPort", "1884")
out = set_prop(out, "httpAdminRoot", "'/admin/v0.7'")
out = set_prop(out, "httpNodeRoot", "'/'")

ui_block = re.search(r"(^\s*)ui\s*:\s*\{([\s\S]*?)\n\s*\}\s*,?", out, re.M)
if ui_block:
    block = ui_block.group(0)
    block2 = re.sub(r"(\bpath\s*:\s*)(['\"]).*?\2", r"\1'ui07'", block)
    if block2 == block:
        block2 = re.sub(r"(ui\s*:\s*\{\s*\n)", r"\1        path: 'ui07',\n", block, count=1)
    out = out.replace(block, block2)

if out != src:
    settings.write_text(out, encoding="utf-8")
    print("patched v07 settings.js")
else:
    print("v07 settings.js already ok")
PY

echo "[5/7] 스냅샷 flows.json 반영"
if [[ -f "${V05_DIR}/merged-v05.json" ]]; then
  [[ -f "${V05_DIR}/flows.json" ]] && cp "${V05_DIR}/flows.json" "${V05_DIR}/flows.v05.backup.$(date +%s).json" || true
  cp "${V05_DIR}/merged-v05.json" "${V05_DIR}/flows.json"
else
  echo "경고: v0.5 스냅샷 파일 없음: ${V05_DIR}/merged-v05.json (v0.5 UI/관리자 경로는 열리지만 내용이 비어있을 수 있음)" >&2
fi

if [[ -f "${V07_DIR}/merged-v07.json" ]]; then
  [[ -f "${V07_DIR}/flows.json" ]] && cp "${V07_DIR}/flows.json" "${V07_DIR}/flows.v07.backup.$(date +%s).json" || true
  cp "${V07_DIR}/merged-v07.json" "${V07_DIR}/flows.json"
else
  # 최초 1회: 최신 flows.json을 복사해 v0.7 스냅샷 씨앗으로 사용
  if [[ -f "${HOME}/.node-red/flows.json" ]]; then
    cp "${HOME}/.node-red/flows.json" "${V07_DIR}/flows.json"
    echo "v0.7: merged-v07.json이 없어 최신 flows.json으로 초기 스냅샷 생성"
  else
    echo "경고: 최신 flows.json이 없어 v0.7 초기 스냅샷을 만들지 못함" >&2
  fi
fi

echo "[6/7] systemd 서비스 구성/재시작"
sudo tee /etc/systemd/system/nodered-v05.service >/dev/null <<EOF
[Unit]
Description=Node-RED (CronusFarm v0.5 snapshot)
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

sudo tee /etc/systemd/system/nodered-v07.service >/dev/null <<EOF
[Unit]
Description=Node-RED (CronusFarm v0.7 snapshot)
After=network.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${HOME}
Environment=NODE_RED_OPTIONS=
ExecStart=/usr/bin/env node-red -u ${V07_DIR}
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now nodered.service nodered-v05.service nodered-v07.service
sudo systemctl restart nodered.service nodered-v05.service nodered-v07.service

echo "[7/7] nginx 프록시 설정(1880)"
sudo tee /etc/nginx/sites-available/cronusfarm-nodered.conf >/dev/null <<'EOF'
map $http_upgrade $connection_upgrade {
  default upgrade;
  ''      close;
}

server {
  listen 1880;
  server_name _;

  # 과거 경로(/farm)는 완전 차단
  location ^~ /farm/ { return 404; }
  location = /farm { return 404; }

  # 스냅샷 내부 경로(ui05/ui07)는 외부 접근 차단(항상 /ui/v0.x 로만 접근)
  location ^~ /ui05/ { return 404; }
  location = /ui05 { return 404; }
  location ^~ /ui07/ { return 404; }
  location = /ui07 { return 404; }

  # 루트(/)는 작업용 UI로 이동
  location = / { return 302 /ui; }

  # 작업용(최신) - 1882
  location ^~ /admin/ {
    proxy_pass http://127.0.0.1:1882/admin/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
  }
  location = /admin { return 301 /admin/; }

  location ^~ /ui/ {
    proxy_pass http://127.0.0.1:1882/ui/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
  }
  location = /ui { return 301 /ui/; }

  # v0.5 스냅샷 - 1881
  location ^~ /admin/v0.5/ {
    proxy_pass http://127.0.0.1:1881/admin/v0.5/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
  }
  location = /admin/v0.5 { return 301 /admin/v0.5/; }

  location ^~ /ui/v0.5/ {
    proxy_pass http://127.0.0.1:1881/ui05/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
  }
  location = /ui/v0.5 { return 301 /ui/v0.5/; }

  # v0.7 스냅샷 - 1883
  location ^~ /admin/v0.7/ {
    proxy_pass http://127.0.0.1:1884/admin/v0.7/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
  }
  location = /admin/v0.7 { return 301 /admin/v0.7/; }

  location ^~ /ui/v0.7/ {
    proxy_pass http://127.0.0.1:1884/ui07/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
  }
  location = /ui/v0.7 { return 301 /ui/v0.7/; }

  # 나머지(HTTP In API 등)는 작업용 Node-RED(httpNodeRoot='/')로 전달
  location / {
    proxy_pass http://127.0.0.1:1882;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
EOF

sudo ln -sf /etc/nginx/sites-available/cronusfarm-nodered.conf /etc/nginx/sites-enabled/cronusfarm-nodered.conf
sudo nginx -t
sudo systemctl restart nginx

echo "OK: /admin, /ui, /admin|ui/v0.5, /admin|ui/v0.7 구성 완료"

