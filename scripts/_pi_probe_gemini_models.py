#!/usr/bin/env python3
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ENV = Path("/etc/cronusfarm/nodered-telegram.env")
env: dict[str, str] = {}
for line in ENV.read_text(encoding="utf-8", errors="replace").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    env[k.strip()] = v.strip()

key = env.get("CRONUSFARM_GEMINI_API_KEY", "")
models = [
    env.get("CRONUSFARM_GEMINI_MODEL", ""),
    "gemini-2.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]
seen: set[str] = set()
payload = json.dumps({"contents": [{"parts": [{"text": "ok"}]}]}).encode("utf-8")

for model in models:
    model = (model or "").strip()
    if not model or model in seen:
        continue
    seen.add(model)
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + urllib.parse.quote(model)
        + ":generateContent?key="
        + urllib.parse.quote(key)
    )
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(model, "->", r.status, "OK")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        msg = ""
        try:
            msg = json.loads(body).get("error", {}).get("message", "")[:120]
        except Exception:
            msg = body[:120]
        print(model, "->", e.code, msg)

print("OPENAI_KEY", "yes" if env.get("CRONUSFARM_OPENAI_API_KEY") else "no")
print("OLLAMA", env.get("CRONUSFARM_OLLAMA_HOST", "http://127.0.0.1:11434"))
