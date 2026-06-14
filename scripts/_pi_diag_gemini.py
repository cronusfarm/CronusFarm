#!/usr/bin/env python3
"""Pi: Gemini env·모델·429 진단 (키는 마스킹)."""
import json
import os
import subprocess
import sys
from pathlib import Path

ENV = Path("/etc/cronusfarm/nodered-telegram.env")
SCRIPT = Path("/home/dooly/CronusFarm/scripts/cronusfarm_telegram_vision.py")


def mask(k: str, v: str) -> str:
    if "KEY" in k or "TOKEN" in k or "SECRET" in k:
        return (v[:4] + "…" + v[-4:]) if len(v) > 10 else "(set)"
    return v


def load_env() -> dict[str, str]:
    out: dict[str, str] = {}
    if ENV.is_file():
        for line in ENV.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip()
    return out


def main() -> int:
    file_env = load_env()
    print("===", ENV)
    for k in sorted(file_env):
        if k.startswith("CRONUSFARM_GEMINI") or k.startswith("CRONUSFARM_VISION"):
            print(f"  file {k}={mask(k, file_env[k])}")

    print("\n=== nodered.service EnvironmentFile")
    r = subprocess.run(
        ["systemctl", "show", "nodered.service", "-p", "EnvironmentFiles", "--value"],
        capture_output=True,
        text=True,
    )
    print(r.stdout.strip() or r.stderr)

    print("\n=== nodered 프로세스 env (GEMINI/VISION만)")
    r2 = subprocess.run(
        ["bash", "-lc", "pid=$(pgrep -f 'node-red' | head -1); tr '\\0' '\\n' < /proc/$pid/environ 2>/dev/null | grep -E '^CRONUSFARM_(GEMINI|VISION)' || true"],
        capture_output=True,
        text=True,
    )
    for line in r2.stdout.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            print(f"  proc {k}={mask(k, v)}")

    print("\n=== script 존재·버전")
    print("  script", SCRIPT.is_file(), SCRIPT)
    if SCRIPT.is_file():
        t = SCRIPT.read_text(encoding="utf-8", errors="replace")
        print("  has _gemini_models_to_try", "_gemini_models_to_try" in t)
        print("  has MSG_429", "MSG_429" in t)

    key = file_env.get("CRONUSFARM_GEMINI_API_KEY", "")
    model = file_env.get("CRONUSFARM_GEMINI_MODEL", "gemini-2.0-flash")
    if not key:
        print("\nWARN: GEMINI_API_KEY 비어 있음")
        return 1

    print("\n=== Gemini API probe (텍스트만, 이미지 없음)")
    import urllib.error
    import urllib.parse
    import urllib.request

    payload = {"contents": [{"parts": [{"text": "ok"}]}]}
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + urllib.parse.quote(model)
        + ":generateContent?key="
        + urllib.parse.quote(key)
    )
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print("  model", model, "HTTP", resp.status, "OK")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:600]
        print("  model", model, "HTTP", e.code, body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
