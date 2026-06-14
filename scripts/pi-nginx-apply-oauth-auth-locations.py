#!/usr/bin/env python3
"""listen 443 + server_name cronusfarm.duckdns.org 블록에만 auth_request /oauth2/auth (변수 미사용).

주의: 이 Pi nginx는 auth_request $변수 미지원 → default_server(80)에 적용 시 500.
"""
from __future__ import annotations

import re
from pathlib import Path

SITE = Path("/etc/nginx/sites-enabled/cronusfarm-nodered.conf")
LOCS = (
    (r"location = /go-settings \{", ""),
    (r"location \^~ /farm/ui/assets/ \{", ""),
    (r"location = /farm/ui/ \{", ""),
    (
        r"location \^~ /farm/ui/ \{",
        "    auth_request_set $auth_email $upstream_http_x_auth_request_email;\n"
        "    add_header X-Auth-User $auth_email;\n",
    ),
    (
        r"location \^~ /farm/cronusfarm-sqlite/ \{",
        "    auth_request_set $auth_email $upstream_http_x_auth_request_email;\n"
        "    auth_request_set $auth_user $upstream_http_x_auth_request_user;\n"
        "    proxy_set_header X-Forwarded-Email $auth_email;\n"
        "    proxy_set_header X-Auth-Request-Email $auth_email;\n"
        "    proxy_set_header X-Auth-Request-User $auth_user;\n",
    ),
    # /ui/ 는 OAuth 제외(해시 #!/1 미전달 → rd=/ui/ 로 설정 SPA 못 감). 모니터는 공개, farm/ui·sqlite 만 보호.
)
AUTH = "    auth_request /oauth2/auth;\n    error_page 401 403 = @oauth2_sign_in;\n"


def _strip_auth(text: str) -> str:
    text = re.sub(r"\n    auth_request[^\n]*\n", "\n", text)
    text = re.sub(r"\n    error_page 401(?: 403)? = @oauth2_sign_in;\n", "\n", text)
    text = re.sub(
        r"\n    auth_request_set \$auth_email[^\n]*\n", "\n", text
    )
    text = re.sub(
        r"\n    add_header X-Auth-User \$auth_email;\n", "\n", text
    )
    text = re.sub(
        r"\n    proxy_set_header X-Forwarded-Email \$auth_email;\n", "\n", text
    )
    text = re.sub(
        r"\n    proxy_set_header X-Auth-Request-Email \$auth_email;\n", "\n", text
    )
    text = re.sub(
        r"\n    auth_request_set \$auth_user[^\n]*\n", "\n", text
    )
    text = re.sub(
        r"\n    proxy_set_header X-Auth-Request-User \$auth_user;\n", "\n", text
    )
    return text


def _should_patch_block(block: str) -> bool:
    if "include /etc/nginx/cronusfarm-oauth2.conf" not in block:
        return False
    if "listen 443" in block and "cronusfarm.duckdns.org" in block:
        return True
    if "listen 80 default_server" in block or "listen 1880 default_server" in block:
        return True
    return False


def _fix_sign_in_redirect(block: str) -> str:
    return block.replace("/oauth2/sign_in?", "/oauth2/start?")


def _patch_block(block: str) -> str:
    if not _should_patch_block(block):
        return block
    block = _fix_sign_in_redirect(block)
    for pat, extra in LOCS:
        m = re.search(pat + r"\s*\n", block)
        if not m:
            continue
        start = m.end()
        chunk = block[start : start + 400]
        if "auth_request /oauth2/auth" in chunk.split("location", 1)[0]:
            continue
        block, n = re.subn(
            "(" + pat + r"\s*\n)",
            r"\1\n" + AUTH + extra,
            block,
            count=0,
        )
        if n:
            print(f"  patched {pat!r}: {n}")
    return block


def main() -> int:
    text = SITE.read_text(encoding="utf-8", errors="replace")
    text = _strip_auth(text)
    parts = re.split(r"(server\s*\{)", text)
    out = [parts[0]]
    i = 1
    while i < len(parts):
        if parts[i].strip() == "server {":
            block = parts[i] + parts[i + 1]
            out.append(_patch_block(block))
            i += 2
        else:
            out.append(parts[i])
            i += 1
    text = "".join(out)
    SITE.write_text(text, encoding="utf-8")
    print("OK", SITE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
