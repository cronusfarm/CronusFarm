# 텔레그램 작물·해충 사진 AI (CronusFarm 봇 확장)

기존 **@CronusFarm_bot** (Node-RED `getUpdates` 폴링)에 **사진 분기**를 붙입니다.  
날씨·텍스트 AI(Ollama)와 **같은 봇·같은 chat_id** 를 씁니다.

## 아키텍처

```text
Telegram 사진
  → cf_fn_tg_dispatch (photo 감지)
  → cf_fn_tg_photo_vision (Pi python3)
  → 작물·해충·방제 답변 → sendMessage
```

## 단계별 로드맵

| 단계 | 내용 | 저장소 |
|------|------|--------|
| **0** | 문서·`cronusfarm_telegram_vision.py`·`patch_telegram_photo_vision.py` | ✅ |
| **1** | merge → Pi NR 배포 + env API 키 | 다음 |
| **2** | **방향 A** Gemini/OpenAI 멀티모달 API 키 (`/etc/cronusfarm/nodered-telegram.env`) | 권장(빠름) |
| **3** | **방향 B** YOLOv8 + Hailo (로컬, `Hailo/`, 기존 경험) | 선택 |
| **4** | 농진청·병해충 예찰 링크/DB를 답변에 자동 첨부 | 선택 |

## 방향 A — 멀티모달 API (권장 시작)

1. [Google AI Studio](https://aistudio.google.com/) 또는 OpenAI API 키 발급  
2. Pi `/etc/cronusfarm/nodered-telegram.env`:

   ```bash
   CRONUSFARM_VISION_PROVIDER=gemini
   CRONUSFARM_GEMINI_API_KEY=...
   CRONUSFARM_GEMINI_MODEL=gemini-2.5-flash-lite
   # 2.0-flash(-lite) 는 무료 한도 0(429)인 키가 많음 — Pi에서 probe 후 2.5 권장
   ```

3. 수동 테스트:

   ```bash
   python3 ~/CronusFarm/scripts/cronusfarm_telegram_vision.py \
     --file-id <telegram_file_id> --chat-id <chat_id>
   ```

4. Node-RED 패치 적용 후 사진 전송 테스트

## 방향 B — YOLOv8 (로컬)

- `cronusfarm_yolov8_training.ipynb`, `Hailo/` 파이프라인 활용  
- 클래스 예: `tomato`, `aphid`, `whitefly`, `spider_mite`  
- 탐지 결과 문자열 → Ollama/gemma 로 방제 문장 생성 (2단계)

## 환경 변수

| 변수 | 의미 |
|------|------|
| `CRONUSFARM_TELEGRAM_BOT_TOKEN` | 기존 봇 토큰 |
| `CRONUSFARM_VISION_PROVIDER` | `gemini` \| `openai` \| `ollama` |
| `CRONUSFARM_GEMINI_API_KEY` | Gemini API |
| `CRONUSFARM_OPENAI_API_KEY` | OpenAI API |
| `CRONUSFARM_OLLAMA_VISION_MODEL` | `llava` 등 (ollama) |
| `CRONUSFARM_VISION_SCRIPT` | NR exec 경로 (기본 repo scripts) |

## Node-RED 적용

```bash
cd ~/CronusFarm
python3 scripts/patch_telegram_photo_vision.py
python3 scripts/merge_nodered_deploy.py --use-split
# NR Import merged-deploy.json → Deploy
sudo systemctl restart nodered.service
```

## 프롬프트 목표 (답변 형식)

1. 추정 작물  
2. 보이는 증상·해충(불확실하면 추가 촬영 안내)  
3. 친환경·화학 방제 요약  
4. 농진청 예찰 참고 링크(고정 URL)

## Gemini 429 (할당량)

- **모델만 바꿔도 안 되는 경우**: API 키의 **2.0 계열 무료 한도가 0** (`limit: 0` in 429 body). `gemini-2.5-flash-lite` 또는 `gemini-flash-lite-latest` 로 변경.
- 확인: `python3 scripts/_pi_probe_gemini_models.py` (Pi에 env 로드 후 각 모델 HTTP 200/429).
- [Google AI rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) · [ai.dev/rate-limit](https://ai.dev/rate-limit)

## 주의

- API 키는 **Pi env만**, git에 올리지 않음  
- 사진은 `/tmp/cf_tg_vision/` 에 임시 저장 후 삭제  
- Pi Ollama `gemma:2b` 는 **비전 불가** — 사진은 gemini/openai/llava 필요
