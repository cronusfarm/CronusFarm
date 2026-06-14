#!/usr/bin/env python3
"""모든 server 블록에서 auth_request / OAuth sign_in 제거."""
from __future__ import annotations

import re
import sys
from pathlib import Path

SITE = Path(sys.argv[1] if len(sys.argv) > 1 else "/etc/nginx/sites-enabled/cronusfarm-nodered.conf")


def _strip_auth(text: str) -> str:
    text = re.sub(r"\n    auth_request[^\n]*\n", "\n", text)
    text = re.sub(r"\n    error_page 401(?: 403)? = @oauth2_sign_in;\n", "\n", text)
    text = re.sub(r"\n    auth_request_set \$auth_email[^\n]*\n", "\n", text)
    text = re.sub(r"\n    auth_request_set \$auth_user[^\n]*\n", "\n", text)
    text = re.sub(r"\n    add_header X-Auth-User \$auth_email;\n", "\n", text)
    text = re.sub(r"\n    proxy_set_header X-Forwarded-Email \$auth_email;\n", "\n", text)
    text = re.sub(r"\n    proxy_set_header X-Auth-Request-Email \$auth_email;\n", "\n", text)
    text = re.sub(r"\n    proxy_set_header X-Auth-Request-User \$auth_user;\n", "\n", text)
    return text


def main() -> int:
    text = SITE.read_text(encoding="utf-8", errors="replace")
    new = _strip_auth(text)
    if new != text:
        SITE.write_text(new, encoding="utf-8")
        print("OK stripped OAuth auth_request from", SITE)
    else:
        print("skip: no OAuth auth_request in", SITE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
