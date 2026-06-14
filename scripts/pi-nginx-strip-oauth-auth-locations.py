#!/usr/bin/env python3
"""default_server(80) 블록에서 auth_request 제거 — 변수 미지원 500 방지."""
from __future__ import annotations

import re
from pathlib import Path

SITE = Path("/etc/nginx/sites-enabled/cronusfarm-nodered.conf")


def _strip_auth(text: str) -> str:
    text = re.sub(r"\n    auth_request[^\n]*\n", "\n", text)
    text = re.sub(r"\n    error_page 401 = @oauth2_sign_in;\n", "\n", text)
    text = re.sub(
        r"\n    auth_request_set \$auth_email[^\n]*\n", "\n", text
    )
    text = re.sub(
        r"\n    auth_request_set \$auth_user[^\n]*\n", "\n", text
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
        r"\n    proxy_set_header X-Auth-Request-User \$auth_user;\n", "\n", text
    )
    return text


def main() -> int:
    text = SITE.read_text(encoding="utf-8", errors="replace")
    parts = re.split(r"(server\s*\{)", text)
    out = [parts[0]]
    i = 1
    while i < len(parts):
        if parts[i].strip() == "server {":
            block = parts[i] + parts[i + 1]
            if "listen 80 default_server" in block or "server_name _" in block:
                block = _strip_auth(block)
                print("  stripped auth from default_server block")
            out.append(block)
            i += 2
        else:
            out.append(parts[i])
            i += 1
    SITE.write_text("".join(out), encoding="utf-8")
    print("OK", SITE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
