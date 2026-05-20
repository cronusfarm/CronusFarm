#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""아침(09:00)·저녁(17:00) 텔레그램 브리핑 수동 발송.

데이터 경로: Open-Meteo · MQTT KMA/AI · SQLite bridge PHW
Pi: sudo bash -lc 'set -a; . /etc/cronusfarm/nodered-telegram.env; set +a; python3 ...'
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from cronusfarm_telegram_briefing import (  # noqa: E402
    build_evening_text,
    build_morning_text,
    collect_context,
)


def telegram_send(token: str, chat_id: str, text: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = json.dumps(
        {"chat_id": int(chat_id), "text": text}, ensure_ascii=False
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return bool(data.get("ok"))
    except Exception as e:
        print(f"telegram_send failed: {e}", file=sys.stderr)
        return False


def main() -> int:
    token = (os.environ.get("CRONUSFARM_TELEGRAM_BOT_TOKEN") or "").strip()
    chat = (os.environ.get("CRONUSFARM_TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat:
        print("ERROR: CRONUSFARM_TELEGRAM_BOT_TOKEN / CHAT_ID 필요", file=sys.stderr)
        return 1

    mode = (sys.argv[1] if len(sys.argv) > 1 else "both").lower()
    ctx = collect_context()
    ok = True

    if mode in ("morning", "am", "09", "both", "all"):
        text = build_morning_text(ctx)
        print("--- 아침(09:00) ---")
        print(text[:200], "...")
        if telegram_send(token, chat, text):
            print("OK morning")
        else:
            ok = False
        time.sleep(1.5)

    if mode in ("evening", "pm", "17", "both", "all"):
        text = build_evening_text(ctx)
        print("--- 저녁(17:00) ---")
        print(text[:200], "...")
        if telegram_send(token, chat, text):
            print("OK evening")
        else:
            ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
