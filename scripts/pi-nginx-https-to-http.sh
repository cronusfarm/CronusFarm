#!/bin/bash
# HTTPS(443)·HTTP→HTTPS(80) 제거 — 전부 HTTP(80) 우선
# 경고: DuckDNS + Google OAuth 와 함께 쓰지 말 것(콜백 403). 되돌리기: pi-nginx-revert-no-oauth.sh
set -eu
ROOT="${HOME}/CronusFarm"
for SITE in \
  /etc/nginx/sites-available/cronusfarm-nodered.conf \
  /etc/nginx/sites-enabled/cronusfarm-nodered.conf; do
  [[ -f "$SITE" ]] || continue
  TS="/etc/nginx/conf.d/cronusfarm-tailscale-443.conf"

  if [[ -f "$ROOT/deploy/nginx/cronusfarm-tailscale-443.conf" ]]; then
    sudo cp "$ROOT/deploy/nginx/cronusfarm-tailscale-443.conf" "$TS"
    echo "OK $TS"
  fi

  if [[ -f "$ROOT/deploy/nginx/cronusfarm-oauth2-full.conf" ]]; then
    sudo cp "$ROOT/deploy/nginx/cronusfarm-oauth2-full.conf" /etc/nginx/cronusfarm-oauth2.conf
  fi

  if [[ -f "$ROOT/deploy/nginx/cronusfarm-nodered.conf" ]]; then
    sudo cp "$ROOT/deploy/nginx/cronusfarm-nodered.conf" "$SITE"
    echo "OK $SITE (저장소 conf)"
  fi

  sudo python3 - "$SITE" <<'PY'
import re
import sys

path = sys.argv[1]
text = open(path, encoding="utf-8").read()
orig = text

# 80 블록: Tailscale *.ts.net → HTTPS
text = re.sub(
    r"\s*# Tailscale MagicDNS: HTTP → HTTPS[^\n]*\n"
    r"\s*if \(\$host ~\* \\.ts\\.net\$\) \{\n"
    r"\s*return 301 https://\$host\$request_uri;\n"
    r"\s*\}\n",
    "\n",
    text,
)

# 80 블록: DuckDNS HTTP→HTTPS (certbot·구버전)
text = re.sub(
    r"\s*set \$cf_http_to_https[^;]*;\n"
    r"(?:\s*if \(\$host = cronusfarm\.duckdns\.org\)[^\n]*\n)*"
    r"(?:\s*if \(\$remote_addr = 127\.0\.0\.1\)[^\n]*\n)*"
    r"(?:\s*if \(\$http_x_forwarded_proto = https\)[^\n]*\n)*"
    r"\s*if \(\$cf_http_to_https = \"1\"\) \{\n"
    r"\s*return 301 https://\$host\$request_uri;\n"
    r"\s*\}\n",
    "\n",
    text,
)

# map: DuckDNS https 고정 제거
text = re.sub(
    r"map \$host \$cf_forwarded_proto \{\n"
    r"\s*cronusfarm\.duckdns\.org https;\n"
    r"\s*default \$cf_xfp_fallback;\n\}",
    "map $host $cf_forwarded_proto {\n  default $cf_xfp_fallback;\n}",
    text,
)
text = re.sub(
    r"map \$host \$cf_oauth_rd_scheme \{\n"
    r"\s*cronusfarm\.duckdns\.org https;\n"
    r"\s*default \$scheme;\n\}",
    "map $host $cf_oauth_rd_scheme {\n  default $scheme;\n}",
    text,
)

# 443 server: 전체를 HTTP 리다이렉트 전용으로 (certbot proxy 제거)
def slim_443_block(block: str) -> str:
    if "listen 443" not in block:
        return block
    m = re.search(r"server_name\s+([^;]+);", block)
    if not m:
        return block
    names = m.group(1).strip()
    ssl = ""
    if "ssl_certificate " in block:
        mc = re.search(
            r"ssl_certificate\s+([^;]+);\s*\n\s*ssl_certificate_key\s+([^;]+);",
            block,
        )
        if mc:
            ssl = (
                f"  ssl_certificate     {mc.group(1)};\n"
                f"  ssl_certificate_key {mc.group(2)};\n"
                "  include /etc/letsencrypt/options-ssl-nginx.conf;\n"
            )
    return (
        "server {\n"
        "  listen 443 ssl;\n"
        "  listen [::]:443 ssl;\n"
        f"  server_name {names};\n\n"
        f"{ssl}"
        "  return 301 http://$host$request_uri;\n"
        "}\n"
    )


parts = re.split(r"(?=\nserver\s*\{)", text)
out = []
n443 = 0
for block in parts:
    if re.search(r"listen\s+443", block):
        out.append(slim_443_block(block))
        n443 += 1
    else:
        out.append(block)
text = "".join(out)

if text != orig:
    open(path, "w", encoding="utf-8").write(text)
    print(f"OK patched {path} (443 blocks→http: {n443})")
else:
    print(f"skip: no nginx redirect changes needed in {path}")
PY

  # certbot managed snippet 이 다시 https 로 밀어올리지 않게
  if command -v certbot >/dev/null 2>&1 \
    && [[ -d /etc/letsencrypt/live/cronusfarm.duckdns.org ]]; then
    sudo certbot install --cert-name cronusfarm.duckdns.org --nginx \
      --no-redirect --non-interactive 2>/dev/null \
      || true
    sudo python3 - "$SITE" <<'PY'
import re, sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
text2 = re.sub(
    r"(\s*)return 301 https://\$host\$request_uri;",
    r"\1return 301 http://$host$request_uri;",
    text,
)
if text2 != text:
    open(path, "w", encoding="utf-8").write(text2)
    print("OK certbot https→http 치환")
PY
  fi
  break
done

sudo nginx -t
sudo systemctl reload nginx
echo "OK pi-nginx-https-to-http.sh — http://cronusfarm.duckdns.org 또는 http://ida.mango-larch.ts.net 사용"
