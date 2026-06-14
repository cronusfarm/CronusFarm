#!/usr/bin/env python3
import os
from pathlib import Path

p = Path("/etc/cronusfarm/nodered-telegram.env")
print("env_file", p.is_file())
if p.is_file():
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

key = os.environ.get("CRONUSFARM_GEMINI_API_KEY", "")
print("key_len", len(key))
print("CAPTION_GEMINI_env", os.environ.get("CRONUSFARM_CAPTION_GEMINI", "(unset)"))
