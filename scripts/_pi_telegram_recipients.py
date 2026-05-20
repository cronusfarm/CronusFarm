#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pi: 텔레그램 수신자·KMA 스냅샷·날씨 env 점검 (토큰은 출력하지 않음)."""
import json
import os
import sys
import urllib.request

ENV = "/etc/cronusfarm/nodered-telegram.env"


def load_env(path: str) -> dict:
    out = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    except OSError as e:
        print("env_read_error", e)
    return out


def main() -> int:
    env = load_env(ENV)
    for k in (
        "CRONUSFARM_TELEGRAM_CHAT_ID",
        "CRONUSFARM_WEATHER_LAT",
        "CRONUSFARM_WEATHER_LON",
        "CRONUSFARM_WEATHER_NAME",
        "CRONUSFARM_KMA_NX",
        "CRONUSFARM_KMA_NY",
    ):
        print(f"{k}={env.get(k, '')}")

    tok = env.get("CRONUSFARM_TELEGRAM_BOT_TOKEN", "")
    if tok:
        try:
            url = f"https://api.telegram.org/bot{tok}/getUpdates?limit=30"
            data = json.load(urllib.request.urlopen(url, timeout=15))
            chats = {}
            for u in data.get("result", []):
                m = u.get("message") or u.get("channel_post") or {}
                c = m.get("chat") or {}
                cid = c.get("id")
                if not cid:
                    continue
                name = c.get("title") or (
                    f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
                )
                chats[str(cid)] = {
                    "type": c.get("type"),
                    "name": name,
                    "username": c.get("username") or "",
                }
            print("recent_chats_json=" + json.dumps(chats, ensure_ascii=False))
        except Exception as e:
            print("getUpdates_error", e)

    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("paho_missing")
        return 0

    got = []

    def on_msg(_c, _u, msg):
        try:
            got.append(json.loads(msg.payload.decode("utf-8")))
        except Exception:
            pass

    try:
        client = mqtt.Client()
    except Exception:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = on_msg
    try:
        client.connect("127.0.0.1", 1883, 60)
        client.subscribe("cronusfarm/kma/snapshot")
        client.loop_start()
        import time

        time.sleep(2)
        client.loop_stop()
        client.disconnect()
    except Exception as e:
        print("mqtt_error", e)
    if got:
        print("kma_snapshot_keys=" + ",".join(sorted(got[-1].keys())))
        print("kma_snapshot_sample=" + json.dumps(got[-1], ensure_ascii=False)[:400])
    else:
        print("kma_snapshot=empty")
    return 0


if __name__ == "__main__":
    sys.exit(main())
