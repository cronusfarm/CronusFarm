#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""대기 중인 텔레그램 메시지 1건을 Ollama로 답변(수동 복구용)."""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ENV = Path("/etc/cronusfarm/nodered-telegram.env")
OFFSET_FILE = Path("/var/lib/cronusfarm/tg_poll_offset.txt")


def load_env() -> dict[str, str]:
    out = dict(os.environ)
    if ENV.is_file():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip("'\"")
    return out


def http_json(url: str, data: dict | None = None, timeout: int = 90) -> dict:
    body = None
    headers = {"User-Agent": "CronusFarm/tg-ai-once"}
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST" if body else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def mqtt_snap(topic: str) -> dict:
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        return {}
    got: list[bytes] = []

    def on_msg(_c, _u, msg):
        got.append(msg.payload)

    try:
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        c = mqtt.Client()
    c.on_message = on_msg
    c.connect("127.0.0.1", 1883, 60)
    c.subscribe(topic)
    c.loop_start()
    import time

    time.sleep(0.6)
    c.loop_stop()
    c.disconnect()
    if not got:
        return {}
    try:
        return json.loads(got[-1].decode("utf-8"))
    except Exception:
        return {}


def pty_label(k: dict) -> str:
    p = k.get("kma_precip_type", k.get("kma_pty"))
    m = {"0": "없음", "1": "비", "2": "비/눈", "3": "눈", "4": "소나기"}
    s = m.get(str(p), str(p) if p not in (None, "") else "미수신")
    try:
        rn = float(k.get("kma_precip_1h"))
        if s in ("없음", "미수신") and rn > 0:
            s = "강우"
    except (TypeError, ValueError):
        pass
    return s


def main() -> int:
    env = load_env()
    token = env.get("CRONUSFARM_TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("ERROR: no bot token", file=sys.stderr)
        return 1
    model = env.get("CRONUSFARM_OLLAMA_MODEL", "gemma:2b").strip()
    host = env.get("CRONUSFARM_OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")

    off = 0
    if OFFSET_FILE.is_file():
        try:
            off = int(OFFSET_FILE.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            off = 0

    base = f"https://api.telegram.org/bot{token}"
    upd = http_json(f"{base}/getUpdates?offset={off}&timeout=0&limit=10", timeout=25)
    items = upd.get("result") or []
    if not items:
        print("NO_PENDING updates (offset=", off, ")")
        return 0

    kma = mqtt_snap("cronusfarm/kma/snapshot")
    phw = mqtt_snap("cronusfarm/phw3988/snapshot") or mqtt_snap("cronusfarm/sensor/phw3988")
    ai = mqtt_snap("cronusfarm/camera/ai_count") or mqtt_snap("cronusfarm/camera/ai_snapshot")

    for u in items:
        uid = int(u.get("update_id", 0))
        off = max(off, uid + 1)
        m = u.get("message") or {}
        chat = (m.get("chat") or {}).get("id")
        text = (m.get("text") or "").strip()
        if not chat or not text:
            continue
        if re.search(r"날씨|기상|예보|weather|강수|바람", text, re.I):
            print("SKIP weather keyword:", text[:40])
            continue

        ctx = "\n".join(
            [
                "농장: 서울 강동구 천호동",
                f"KMA: {kma.get('kma_temp','—')}°C 습도 {kma.get('kma_humidity','—')}% 강수 {pty_label(kma)}",
                f"PHW: pH {phw.get('ph','—')} EC {phw.get('ec','—')}",
                f"CCTV: {ai.get('count', ai.get('caption','—'))}",
            ]
        )
        prompt = f"한국어로 간결히 답하세요.\n[현장]\n{ctx}\n\n[질문]\n{text}"
        gen = http_json(
            f"{host}/api/generate",
            {"model": model, "prompt": prompt, "stream": False, "options": {"num_predict": 420}},
            timeout=120,
        )
        ans = (gen.get("response") or "응답 없음").strip()[:3500]
        send = http_json(
            f"{base}/sendMessage",
            {"chat_id": int(chat), "text": ans},
            timeout=25,
        )
        print("OK chat", chat, "send", send.get("ok"), "len", len(ans))

    OFFSET_FILE.parent.mkdir(parents=True, exist_ok=True)
    OFFSET_FILE.write_text(str(off), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
