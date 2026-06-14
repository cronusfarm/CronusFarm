#!/usr/bin/env bash
# Pi: 텔레그램 안내 메시지 1회 발송
set -euo pipefail
MSG="${1:-봇 연결이 복구되었습니다. 같은 질문을 다시 보내 주세요.}"
sudo python3 <<PY
import json, os, urllib.request
from pathlib import Path
env = {}
for line in Path("/etc/cronusfarm/nodered-telegram.env").read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip("'\"")
token = env.get("CRONUSFARM_TELEGRAM_BOT_TOKEN", "")
chat = env.get("CRONUSFARM_TELEGRAM_CHAT_ID", "")
if not token or not chat:
    raise SystemExit("token/chat_id 없음")
url = f"https://api.telegram.org/bot{token}/sendMessage"
body = json.dumps({"chat_id": int(chat), "text": """$MSG"""[:3500]}).encode()
req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=25) as r:
    print(r.read().decode()[:200])
PY
