#!/usr/bin/env bash
# server_name _ (80) 블록: *.ts.net 만 HTTP→HTTPS (OAuth map default "" 로 443 무인증)
set -euo pipefail
SITE="/etc/nginx/sites-enabled/cronusfarm-nodered.conf"
MARK="Tailscale MagicDNS: HTTP → HTTPS"

if grep -q "$MARK" "$SITE" 2>/dev/null; then
  echo "skip: already present"
  exit 0
fi

sudo python3 <<'PY'
import re
from pathlib import Path

site = Path("/etc/nginx/sites-enabled/cronusfarm-nodered.conf")
text = site.read_text(encoding="utf-8")
mark = "Tailscale MagicDNS: HTTP → HTTPS"
snippet = (
    "  # " + mark + " (Google OAuth 없음 — 443 map default \"\")\n"
    "  if ($host ~* \\.ts\\.net$) {\n"
    "    return 301 https://$host$request_uri;\n"
    "  }\n\n"
)
parts = re.split(r"(server\s*\{)", text)
out = [parts[0]]
i = 1
done = False
while i < len(parts):
    if parts[i].strip() == "server {" and not done:
        block = parts[i] + parts[i + 1]
        if "server_name _;" in block and "listen 80 default_server" in block:
            block, n = re.subn(
                r"(# 루트\(/\)[^\n]*\n\s*location = / \{ return 301 /ui/; \})",
                snippet + r"\1",
                block,
                count=1,
            )
            if n:
                done = True
                print("inserted ts.net http->https")
        out.append(block)
        i += 2
    elif parts[i].strip() == "server {":
        out.append(parts[i] + parts[i + 1])
        i += 2
    else:
        out.append(parts[i])
        i += 1
if not done:
    raise SystemExit("server_name _ block not found")
site.write_text("".join(out), encoding="utf-8")
PY

sudo nginx -t
sudo systemctl reload nginx
echo "OK tailscale http->https"
