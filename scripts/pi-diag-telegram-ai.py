#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pi: 텔레그램 getUpdates·Ollama·Node-RED env 진단."""
from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path


def load_env() -> dict[str, str]:
    out = dict(os.environ)
    p = Path("/etc/cronusfarm/nodered-telegram.env")
    if p.is_file():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip("'\"")
    dropin = Path("/etc/systemd/system/nodered.service.d")
    if dropin.is_dir():
        for conf in sorted(dropin.glob("*.conf")):
            for line in conf.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.strip().startswith("Environment="):
                    raw = line.strip()[len("Environment=") :].strip().strip('"')
                    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", raw)
                    if m:
                        out[m.group(1)] = m.group(2)
    return out


def main() -> None:
    env = load_env()
    token = env.get("CRONUSFARM_TELEGRAM_BOT_TOKEN", "")
    print("TOKEN_LEN", len(token))
    print("OLLAMA", env.get("CRONUSFARM_OLLAMA_ENABLED"), env.get("CRONUSFARM_OLLAMA_MODEL"))
    if not token:
        print("ERROR: no bot token")
        return
    url = f"https://api.telegram.org/bot{token}/getUpdates?offset=-5&limit=5"
    with urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "CronusFarm/diag"}),
        timeout=25,
    ) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    print("getUpdates ok=", data.get("ok"), "count=", len(data.get("result") or []))
    for u in data.get("result") or []:
        m = u.get("message") or {}
        print(
            " update_id=",
            u.get("update_id"),
            "chat=",
            (m.get("chat") or {}).get("id"),
            "text=",
            (m.get("text") or "")[:80],
        )
    # Ollama
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5) as r:
            tags = json.loads(r.read().decode())
        print("ollama models:", [x.get("name") for x in tags.get("models", [])])
    except Exception as e:
        print("ollama ERR", e)


if __name__ == "__main__":
    main()
