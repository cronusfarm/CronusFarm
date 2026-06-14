# -*- coding: utf-8 -*-
"""텔레그램 브리핑 데이터 취합·메시지 템플릿 (아침 Open-Meteo / 저녁 통합)."""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
PTY_MAP = {
    "0": "없음",
    "1": "비",
    "2": "비/눈",
    "3": "눈",
    "4": "소나기",
    "5": "빗방울",
    "6": "빗방울눈날림",
    "7": "눈날림",
}


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def kma_pty_label(v) -> str:
    if v is None or v == "":
        return "미수신"
    return PTY_MAP.get(str(v), str(v))


def kma_precip_display(kma: dict) -> tuple[str, str, str]:
    """강수형태·1h강수·관측 신선도. RN1>0 인데 PTY=0 이면 '강우'로 보정."""
    pty_raw = kma.get("kma_precip_type", kma.get("kma_pty", ""))
    pcp = kma.get("kma_precip_1h")
    label = kma_pty_label(pty_raw)
    try:
        rn = float(pcp) if pcp is not None and pcp != "" else None
    except (TypeError, ValueError):
        rn = None
    if label in ("없음", "미수신") and rn is not None and rn > 0:
        label = "강우"
    if pcp is None:
        pcp_show = "0" if label == "없음" else "미수신"
    else:
        pcp_show = str(pcp)
    stale = ""
    ts = kma.get("ts")
    if ts:
        age_h = (time.time() * 1000 - float(ts)) / 3600000.0
        if age_h > 6:
            stale = f" (KMA 관측 {age_h:.0f}시간 전 — 갱신 필요)"
    return label, pcp_show, stale


def fmt_kst_ms(ms) -> str:
    if not ms:
        return "미수신"
    d = datetime.fromtimestamp(float(ms) / 1000.0, tz=KST)
    return d.strftime("%Y-%m-%d %H:%M:%S KST")


def mqtt_retain_json(topic: str, host: str = "127.0.0.1", port: int = 1883) -> dict:
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        return {}
    got: list[dict] = []

    def on_msg(_c, _u, msg):
        try:
            got.append(json.loads(msg.payload.decode("utf-8")))
        except Exception:
            pass

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        client = mqtt.Client()
    client.on_message = on_msg
    try:
        client.connect(host, port, 60)
        client.subscribe(topic)
        client.loop_start()
        time.sleep(2.0)
        client.loop_stop()
        client.disconnect()
    except Exception:
        return {}
    return got[-1] if got else {}


def fetch_open_meteo(lat: str, lon: str) -> dict | None:
    if not lat or not lon:
        return None
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={urllib.parse.quote(lat)}"
        f"&longitude={urllib.parse.quote(lon)}"
        "&current=temperature_2m,relative_humidity_2m,precipitation,weather_code"
        "&hourly=precipitation&forecast_days=1&timezone=Asia%2FSeoul"
    )
    try:
        with urllib.request.urlopen(url, timeout=25) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def fetch_sensor_latest(
    bridge: str = "http://127.0.0.1:18766",
    device_id: str = "cronusfarm-01",
    zone: str = "phw3988",
) -> dict:
    url = (
        f"{bridge.rstrip('/')}/api/sensor/latest"
        f"?device_id={urllib.parse.quote(device_id)}&zone={urllib.parse.quote(zone)}"
    )
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {}


def collect_context() -> dict:
    """여러 경로에서 스냅샷 취합."""
    kma = mqtt_retain_json("cronusfarm/kma/snapshot")
    if kma:
        if kma.get("kma_precip_type") is None and kma.get("kma_pty") is not None:
            kma["kma_precip_type"] = kma["kma_pty"]
    ai = mqtt_retain_json("cronusfarm/camera/ai_count")
    phw = fetch_sensor_latest()
    return {
        "kma": kma,
        "ai": ai,
        "phw": phw if phw.get("ok") else {},
        "weather_lat": _env("CRONUSFARM_WEATHER_LAT"),
        "weather_lon": _env("CRONUSFARM_WEATHER_LON"),
        "weather_name": _env("CRONUSFARM_WEATHER_NAME", "CronusFarm"),
    }


def build_morning_text(ctx: dict | None = None) -> str:
    ctx = ctx or collect_context()
    lat = ctx["weather_lat"]
    lon = ctx["weather_lon"]
    name = ctx["weather_name"]
    now = datetime.now(KST)
    title = f"🌞 {now.month:02d}월 {now.day:02d}일 농업 정보"
    if name:
        title += f" ({name})"

    if not lat or not lon:
        return (
            f"{title}\n\n"
            "날씨 위치가 설정되어 있지 않습니다.\n"
            "/etc/cronusfarm/nodered-telegram.env 에\n"
            "CRONUSFARM_WEATHER_LAT / LON 을 설정해 주세요."
        )

    data = fetch_open_meteo(lat, lon)
    if not data or "current" not in data:
        return f"{title}\n\n날씨 API 응답을 받지 못했습니다."

    wdesc = {
        0: ("맑음", "🌤️"),
        61: ("비", "🌧️"),
        80: ("소나기", "🌦️"),
    }
    cur = data["current"]
    t = float(cur["temperature_2m"])
    hum = float(cur["relative_humidity_2m"])
    wc = int(cur.get("weather_code") or 0)
    wd_label, wd_icon = wdesc.get(wc, ("날씨", "🌤️"))
    p1 = 0.0
    try:
        hourly = data.get("hourly", {}).get("precipitation", [])
        p1 = float(hourly[max(0, min(len(hourly) - 1, now.hour))] or 0)
    except (TypeError, ValueError, IndexError):
        pass

    lines = [
        title,
        "",
        f"{wd_icon} {wd_label} | 🌡️ {t:.1f}°C | 💧 {round(hum)}% | ☔ 1h {p1:.1f}mm",
        "",
        "📋 브리핑:",
        f"1. 습도 {round(hum)}% — 목표 범위 유지",
        f"2. 기온 {t:.1f}°C — 오후·야간 대비",
        "3. 강수·환기·병해 예방 점검",
        "",
        "━━━━━━━━━━━━━━━━",
    ]
    return "\n".join(lines)


def build_evening_text(ctx: dict | None = None) -> str:
    ctx = ctx or collect_context()
    kma = ctx.get("kma") or {}
    ai = ctx.get("ai") or {}
    phw = ctx.get("phw") or {}
    now = datetime.now(KST)

    temp = kma.get("kma_temp", "미수신")
    hum = kma.get("kma_humidity", "미수신")
    pty, pcp, stale_note = kma_precip_display(kma)
    obs = ""
    if kma.get("base_date") and kma.get("base_time"):
        bd = str(kma["base_date"])
        bt = str(kma["base_time"]).zfill(4)
        obs = f"{bd[:4]}.{bd[4:6]}.{bd[6:8]} {bt[:2]}:{bt[2:4]} KST"

    # PHW3988 센서 (SQLite bridge /ingest 동일 경로)
    def _phw_val(key: str):
        v = phw.get(key)
        if v is None or v == "":
            return "미수신"
        if isinstance(v, float):
            return f"{v:.2f}".rstrip("0").rstrip(".")
        return str(v)

    ph = _phw_val("ph")
    ec = _phw_val("ec")
    wtemp = _phw_val("temp_c")
    ai_count = ai.get("count", "미수신")
    ai_cap = (ai.get("caption") or "").strip() or "미수신"

    t_s = "" if temp == "미수신" else "°C"
    h_s = "" if hum == "미수신" else "%"
    p_s = "" if pcp == "미수신" else "mm"
    w_s = "" if wtemp == "미수신" else "°C"

    return (
        f"🌙 {now.month:02d}월 {now.day:02d}일 저녁 영농 준비\n\n"
        f"🌤️ KMA: 🌡️ {temp}{t_s} | 💧 {hum}{h_s} | 🌧️ {pty} | ☔ 1h {pcp}{p_s}{stale_note}\n"
        f"🛰️ 관측: {obs or '미수신'}\n\n"
        f"🧪 PHW3988(센서): pH {ph} | EC {ec} µS/cm | 수온 {wtemp}{w_s}\n\n"
        f"📷 CCTV AI: {ai_count}개 — {ai_cap}\n\n"
        "📋 점검\n"
        "• tele/status·펌프가드(G) 수신 확인\n"
        "• 스케줄/수동(auto_*) 유지 여부"
    )
