#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""텔레그램 사진 → 작물·해충·방제 안내 (Gemini/OpenAI/Ollama 비전).

사용:
  python3 cronusfarm_telegram_vision.py --file /path/to.jpg
  python3 cronusfarm_telegram_vision.py --file-id <id> --chat-id <optional>

환경: /etc/cronusfarm/nodered-telegram.env 또는 CRONUSFARM_* 변수
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PROMPT = """당신은 시설원예·노지 농업 전문가입니다. 한국어로 답하세요.

사진을 보고 다음을 순서대로 짧게 정리하세요.
1) 추정 작물
2) 보이는 증상·의심 해충/병해(불확실하면 추가 촬영·확대 안내)
3) 즉시 조치·예방(친환경 우선, 필요 시 약제는 일반명만)
4) 참고: 농촌진흥청 병해충 예찰 https://www.nongsaro.go.kr

400~800자 이내, 불확실하면 추측이라고 명시."""

PEST_LINK = "https://www.nongsaro.go.kr/portal/ps/psb/psbb/farmPestForecastList.ps?menuId=PS04101"

MSG_429 = (
    "⚠️ Gemini API 할당량 초과(HTTP 429)입니다.\n"
    "· 잠시(1~2분) 후 사진을 다시 보내 주세요.\n"
    "· 2.0-flash(-lite) 무료 한도가 0이면 2.5 모델로 변경:\n"
    "  CRONUSFARM_GEMINI_MODEL=gemini-2.5-flash-lite\n"
    "· Google AI Studio: https://ai.dev/rate-limit (결제·일일 한도)\n"
    "· 대안: OPENAI 키 또는 Pi에서 ollama pull llava"
)


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        if not k:
            continue
        # Pi env 파일이 nodered 상속값보다 우선 (모델 변경 후 재시작 없이도 스크립트 단독 실행 시 반영)
        os.environ[k] = v.strip()


def tg_token() -> str:
    t = (os.environ.get("CRONUSFARM_TELEGRAM_BOT_TOKEN") or "").strip()
    if not t:
        raise RuntimeError("CRONUSFARM_TELEGRAM_BOT_TOKEN 없음")
    return t


def download_telegram_photo(file_id: str, dest: Path) -> Path:
    token = tg_token()
    url = f"https://api.telegram.org/bot{token}/getFile?file_id={urllib.parse.quote(file_id)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    if not data.get("ok"):
        raise RuntimeError(f"getFile 실패: {data}")
    fp = data["result"]["file_path"]
    dl = f"https://api.telegram.org/file/bot{token}/{fp}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(dl, timeout=60) as r:
        dest.write_bytes(r.read())
    return dest


def send_telegram(chat_id: int, text: str) -> None:
    token = tg_token()
    body = json.dumps({"chat_id": chat_id, "text": text[:4000]}).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        out = json.loads(r.read().decode("utf-8"))
    if not out.get("ok"):
        raise RuntimeError(f"sendMessage 실패: {out}")


def _http_error_detail(e: urllib.error.HTTPError) -> str:
    try:
        return e.read().decode("utf-8", errors="replace")[:800]
    except Exception:
        return str(e)


def _is_rate_limit(e: BaseException) -> bool:
    if isinstance(e, urllib.error.HTTPError) and e.code == 429:
        return True
    return "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "rate limit" in str(e).lower()


def build_prompt(extra_question: str = "") -> str:
    q = (extra_question or "").strip()
    if not q:
        return PROMPT
    return (
        PROMPT
        + "\n\n[사용자 추가 질문]\n"
        + q
        + "\n(위 질문에 우선 답하되, 형식은 동일하게 유지.)"
    )


def analyze_gemini(image_path: Path, prompt: str, model: str | None = None) -> str:
    key = (os.environ.get("CRONUSFARM_GEMINI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("CRONUSFARM_GEMINI_API_KEY 없음")
    model = (model or os.environ.get("CRONUSFARM_GEMINI_MODEL") or "gemini-2.5-flash-lite").strip()
    b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    mime = "image/jpeg"
    if image_path.suffix.lower() == ".png":
        mime = "image/png"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime, "data": b64}},
                ]
            }
        ]
    }
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{urllib.parse.quote(model)}:generateContent?key={urllib.parse.quote(key)}"
    )
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode("utf-8"))
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Gemini 응답 파싱 실패: {data}") from e


def analyze_openai(image_path: Path, prompt: str) -> str:
    key = (os.environ.get("CRONUSFARM_OPENAI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("CRONUSFARM_OPENAI_API_KEY 없음")
    model = (os.environ.get("CRONUSFARM_OPENAI_VISION_MODEL") or "gpt-4o-mini").strip()
    b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    mime = "image/jpeg"
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                ],
            }
        ],
        "max_tokens": 900,
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


def analyze_ollama(image_path: Path, prompt: str) -> str:
    host = (os.environ.get("CRONUSFARM_OLLAMA_HOST") or "http://127.0.0.1:11434").rstrip("/")
    model = (os.environ.get("CRONUSFARM_OLLAMA_VISION_MODEL") or "llava").strip()
    b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [b64],
        "stream": False,
    }
    req = urllib.request.Request(
        f"{host}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read().decode("utf-8"))
    text = (data.get("response") or "").strip()
    if not text:
        raise RuntimeError("Ollama 비전 응답 없음 — llava 등 비전 모델 설치 확인")
    return text


def _gemini_models_to_try() -> list[str]:
    primary = (os.environ.get("CRONUSFARM_GEMINI_MODEL") or "gemini-2.5-flash-lite").strip()
    fallbacks = (
        os.environ.get("CRONUSFARM_GEMINI_FALLBACK_MODELS")
        or "gemini-flash-lite-latest,gemini-2.5-flash-lite,gemini-2.0-flash-lite"
    ).split(",")
    out: list[str] = []
    for m in [primary, *fallbacks]:
        m = m.strip()
        if m and m not in out:
            out.append(m)
    return out


def analyze(image_path: Path, extra_question: str = "") -> str:
    prompt = build_prompt(extra_question)
    provider = (os.environ.get("CRONUSFARM_VISION_PROVIDER") or "gemini").strip().lower()
    errors: list[str] = []

    def run_gemini() -> str:
        last: BaseException | None = None
        for model in _gemini_models_to_try():
            for attempt in range(2):
                try:
                    return analyze_gemini(image_path, prompt, model=model)
                except urllib.error.HTTPError as e:
                    last = e
                    if e.code == 429 and attempt == 0:
                        wait = 25
                        if e.headers.get("Retry-After"):
                            try:
                                wait = min(60, max(5, int(e.headers["Retry-After"])))
                            except ValueError:
                                pass
                        time.sleep(wait)
                        continue
                    raise
                except Exception as e:
                    last = e
                    if _is_rate_limit(e):
                        break
                    raise
            if last and _is_rate_limit(last):
                continue
        if last:
            raise last
        raise RuntimeError("Gemini 모델 시도 실패")

    try:
        if provider == "openai":
            body = analyze_openai(image_path, prompt)
        elif provider == "ollama":
            body = analyze_ollama(image_path, prompt)
        else:
            body = run_gemini()
    except Exception as primary_err:
        errors.append(f"{provider}: {primary_err}")
        if _is_rate_limit(primary_err) and provider == "gemini":
            openai_key = (os.environ.get("CRONUSFARM_OPENAI_API_KEY") or "").strip()
            if openai_key:
                try:
                    body = analyze_openai(image_path, prompt)
                except Exception as e2:
                    errors.append(f"openai fallback: {e2}")
                    body = MSG_429
                else:
                    if PEST_LINK not in body:
                        body += f"\n\n예찰·예보: {PEST_LINK}"
                    return body
            else:
                body = MSG_429
            if PEST_LINK not in body:
                body += f"\n\n예찰·예보: {PEST_LINK}"
            return body
        if provider != "ollama":
            try:
                body = analyze_ollama(image_path, prompt)
            except Exception as e3:
                errors.append(f"ollama fallback: {e3}")
                if _is_rate_limit(primary_err):
                    body = MSG_429
                else:
                    detail = _http_error_detail(primary_err) if isinstance(primary_err, urllib.error.HTTPError) else str(primary_err)
                    body = f"AI 분석 실패: {detail[:500]}"
        else:
            detail = _http_error_detail(primary_err) if isinstance(primary_err, urllib.error.HTTPError) else str(primary_err)
            body = f"AI 분석 실패: {detail[:500]}"

    if PEST_LINK not in body:
        body += f"\n\n예찰·예보: {PEST_LINK}"
    return body


def main() -> int:
    ap = argparse.ArgumentParser(description="CronusFarm 텔레그램 사진 AI")
    ap.add_argument("--file", help="로컬 이미지 경로")
    ap.add_argument("--file-id", help="Telegram file_id")
    ap.add_argument("--chat-id", type=int, default=0, help="지정 시 Telegram으로 전송")
    ap.add_argument("--send", action="store_true", help="--chat-id 와 함께 전송")
    ap.add_argument("--question", default="", help="사진 캡션·추가 질문(예: 작물 이름)")
    args = ap.parse_args()

    load_env_file(Path("/etc/cronusfarm/nodered-telegram.env"))

    if args.file:
        img = Path(args.file)
    elif args.file_id:
        img = Path(f"/tmp/cf_tg_vision/{re.sub(r'[^a-zA-Z0-9_-]', '_', args.file_id)}.jpg")
        download_telegram_photo(args.file_id, img)
    else:
        print("ERROR: --file 또는 --file-id 필요", file=sys.stderr)
        return 2

    if not img.is_file():
        print(f"ERROR: 이미지 없음 {img}", file=sys.stderr)
        return 2

    try:
        text = analyze(img, (args.question or "").strip())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            text = MSG_429
        else:
            text = f"AI 분석 HTTP {e.code}: {_http_error_detail(e)[:500]}"
    except Exception as e:
        if _is_rate_limit(e):
            text = MSG_429
        else:
            text = f"AI 분석 실패: {e}\n\n설정: CRONUSFARM_VISION_PROVIDER=gemini + API 키, 또는 ollama pull llava"

    print(text)
    cid = args.chat_id or int((os.environ.get("CRONUSFARM_TELEGRAM_CHAT_ID") or "0"))
    if args.send and cid:
        send_telegram(cid, text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
