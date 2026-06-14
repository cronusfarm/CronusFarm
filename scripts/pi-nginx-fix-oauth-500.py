#!/usr/bin/env python3
"""auth_request 빈 URI(500)·ingest OAuth 오적용 복구."""
from __future__ import annotations

import re
from pathlib import Path

SITE = Path("/etc/nginx/sites-enabled/cronusfarm-nodered.conf")
OAUTH = Path("/etc/nginx/cronusfarm-oauth2.conf")

INGEST_LOC = """  location ^~ /farm/cronusfarm-sqlite/ingest/ {
    proxy_pass http://127.0.0.1:18766/ingest/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 5s;
    proxy_read_timeout 60s;
    proxy_send_timeout 60s;
  }

"""

AUTH_SKIP = """
location = /oauth2/auth_skip {
  internal;
  return 204;
}
"""


def main() -> int:
    text = SITE.read_text(encoding="utf-8", errors="replace")
    text = re.sub(
        r"map \$host \$cf_oauth_auth_uri \{[^}]+\}",
        "map $host $cf_oauth_auth_uri {\n"
        "  cronusfarm.duckdns.org /oauth2/auth;\n"
        "  default /oauth2/auth_skip;\n"
        "}",
        text,
        count=1,
    )
    if "/farm/cronusfarm-sqlite/ingest/" not in text:
        text = text.replace(
            "  location ^~ /farm/cronusfarm-sqlite/ {",
            INGEST_LOC + "  location ^~ /farm/cronusfarm-sqlite/ {",
            1,
        )
        print("  added ingest location (no OAuth)")
    # ingest 블록에 잘못 붙은 auth 제거
    text = re.sub(
        r"(location \^~ /farm/cronusfarm-sqlite/ingest/ \{.*?)(\n    auth_request[^\n]*\n)+",
        r"\1\n",
        text,
        count=1,
        flags=re.DOTALL,
    )
    SITE.write_text(text, encoding="utf-8")
    print("OK map + ingest", SITE)

    if OAUTH.is_file():
        oauth = OAUTH.read_text(encoding="utf-8", errors="replace")
        if "oauth2/auth_skip" not in oauth:
            oauth = AUTH_SKIP.strip() + "\n\n" + oauth
            OAUTH.write_text(oauth, encoding="utf-8")
            print("OK auth_skip in", OAUTH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
