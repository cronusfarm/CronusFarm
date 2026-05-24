#!/usr/bin/env python3
"""cronusfarm.duckdns.org server 블록에만 auth_request /oauth2/auth 적용."""
from __future__ import annotations

import re
from pathlib import Path

SITE = Path("/etc/nginx/sites-enabled/cronusfarm-nodered.conf")
LOCS = (
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
        "    proxy_set_header X-Forwarded-Email $auth_email;\n",
    ),
    (
        r"location \^~ /ui/ \{",
        "    auth_request_set $auth_email $upstream_http_x_auth_request_email;\n"
        "    proxy_set_header X-Forwarded-Email $auth_email;\n",
    ),
)
AUTH = "    auth_request $cf_oauth_auth_uri;\n    error_page 401 = @oauth2_sign_in;\n"


def _strip_auth(text: str) -> str:
    text = re.sub(r"\n    auth_request[^\n]*\n", "\n", text)
    text = re.sub(r"\n    error_page 401 = @oauth2_sign_in;\n", "\n", text)
    text = re.sub(
        r"\n    auth_request_set \$auth_email[^\n]*\n", "\n", text
    )
    text = re.sub(
        r"\n    add_header X-Auth-User \$auth_email;\n", "\n", text
    )
    text = re.sub(
        r"\n    proxy_set_header X-Forwarded-Email \$auth_email;\n", "\n", text
    )
    return text


def _patch_block(block: str) -> str:
    if "server_name cronusfarm.duckdns.org" not in block:
        return block
    if "listen 443" not in block:
        return block
    for pat, extra in LOCS:
        m = re.search(pat + r"\s*\n", block)
        if not m:
            continue
        start = m.end()
        chunk = block[start : start + 400]
        if "auth_request $cf_oauth_auth_uri" in chunk.split("location", 1)[0]:
            continue
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
