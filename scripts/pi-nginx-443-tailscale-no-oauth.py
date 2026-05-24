#!/usr/bin/env python3
"""443: Tailscale(*.ts.net) 무OAuth / DuckDNS만 auth_request /oauth2/auth."""
from __future__ import annotations

import re
from pathlib import Path

SITE = Path("/etc/nginx/sites-enabled/cronusfarm-nodered.conf")
MARK = "# CRONUSFARM_443_TAILSCALE_DEV"
SSL_SNIPPET = """
    listen 443 ssl default_server;
    listen [::]:443 ssl default_server;
    ssl_certificate /etc/letsencrypt/live/cronusfarm.duckdns.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/cronusfarm.duckdns.org/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
"""


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


def _extract_brace_block(text: str, start: int) -> str | None:
    i = start
    depth = 0
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
        i += 1
    return None


def _first_server_block(text: str) -> str | None:
    marker = "server {\n  # 표준 HTTP(80)"
    pos = text.find(marker)
    if pos < 0:
        pos = text.find("server {\n  # 표준 HTTP")
    if pos < 0:
        return None
    return _extract_brace_block(text, pos)


def _restore_duckdns_auth(block: str) -> str:
    """DuckDNS 443 블록: 변수 auth → 고정 /oauth2/auth (nginx 변수 auth 미지원)."""
    if "listen 443" not in block or "cronusfarm.duckdns.org" not in block:
        return block
    block = block.replace(
        "auth_request $cf_oauth_auth_uri;",
        "auth_request /oauth2/auth;",
    )
    return block


def main() -> int:
    text = SITE.read_text(encoding="utf-8", errors="replace")
    if MARK in text:
        print("skip: tailscale 443 block exists")
        return 0

    base = _first_server_block(text)
    if not base:
        raise SystemExit("server_name _ block not found")

    # HTTP 전용 if (ts.net→https) 제거한 443 본문
    body = base
    body = re.sub(
        r"\n\s*listen 80[^\n]*\n\s*listen \[::\]:80[^\n]*\n"
        r"\s*listen 1880[^\n]*\n\s*listen \[::\]:1880[^\n]*\n",
        "\n",
        body,
        count=1,
    )
    body = re.sub(
        r"\n\s*# Tailscale MagicDNS: HTTP → HTTPS[^\n]*\n"
        r"\s*if \(\$host ~\* \\.ts\\.net\$\) \{[^\}]*\}\n",
        "\n",
        body,
        count=1,
    )
    body = body.replace("server_name _;", "server_name _ ~\\.ts\\.net$;")
    body = _strip_auth(body)
    inner = body[body.find("{") + 1 : body.rfind("}")]
    new_server = (
        "server {\n"
        f"  {MARK}\n"
        "  # Tailscale/LAN HTTPS — Google OAuth 없음 (VPN만)\n"
        + SSL_SNIPPET
        + inner
        + "}\n\n"
    )

    # DuckDNS 443: default_server 제거 + auth 고정
    parts = re.split(r"(server\s*\{)", text)
    out = [parts[0]]
    i = 1
    inserted = False
    while i < len(parts):
        if parts[i].strip() == "server {":
            block = parts[i] + parts[i + 1]
            block = _restore_duckdns_auth(block)
            if (
                not inserted
                and "listen 443" in block
                and "cronusfarm.duckdns.org" in block
            ):
                out.append(new_server)
                inserted = True
                block = re.sub(
                    r"\n\s*listen 443 ssl default_server;\n",
                    "\n    listen 443 ssl;\n",
                    block,
                )
                block = re.sub(
                    r"\n\s*listen \[::\]:443 ssl default_server;\n",
                    "\n    listen [::]:443 ssl ipv6only=on;\n",
                    block,
                )
            out.append(block)
            i += 2
        else:
            out.append(parts[i])
            i += 1

    if not inserted:
        out.append(new_server)

    text = "".join(out)
    text = text.replace(
        "auth_request $cf_oauth_auth_uri;",
        "auth_request /oauth2/auth;",
    )
    SITE.write_text(text, encoding="utf-8")
    print("OK", SITE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
