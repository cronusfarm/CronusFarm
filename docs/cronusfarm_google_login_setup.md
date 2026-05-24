# CronusFarm Google 로그인 (cronusfarm.duckdns.org)

| 접속 | Google 로그인 |
|------|----------------|
| **Tailscale** `http://ida.mango-larch.ts.net/...` | **불필요** — Tailscale VPN·기기 인증만 |
| **공개** `https://cronusfarm.duckdns.org/...` | **필수** — oauth2-proxy (nginx `$host` 기준) |

공개 웹 UI·관리 API 설정은 **`https://cronusfarm.duckdns.org`** 기준으로 진행합니다.

## 1. HTTPS (라우터 443 열림 후)

Pi SSH:

```bash
# 선택: Let's Encrypt 알림용 이메일
export CERTBOT_EMAIL=you@gmail.com
bash ~/CronusFarm/scripts/pi-setup-duckdns-https.sh
```

확인: 브라우저 `https://cronusfarm.duckdns.org/farm/ui/` (루트 `/` 도 farm-ui 로 이동)

## 2. API 키 vs OAuth 클라이언트 (다름)

| | **API 키** (Gemini·텔레그램 AI) | **OAuth Web 클라이언트** (웹 로그인) |
|--|-------------------------------|-----------------------------------|
| 용도 | 서버→Google API 호출 | **사용자**가 브라우저로 Google 로그인 |
| 예 | `CRONUSFARM_GEMINI_API_KEY` | `OAUTH2_PROXY_CLIENT_ID` / `SECRET` |
| 만드는 곳 | API 및 서비스 → 사용자 인증 정보 → **API 키** | 동의 화면 + **OAuth 클라이언트 ID → 웹 애플리케이션** |
| Redirect URI | 없음 | **필수** (`…/oauth2/callback`) |

텔레그램 사진 AI용 API 키를 **그대로** oauth2-proxy에 넣으면 동작하지 않습니다.

## 3. Google Cloud Console — OAuth Web 클라이언트

1. [Google Cloud Console](https://console.cloud.google.com/) → **API 및 서비스** → **OAuth 동의 화면** (테스트 사용자에 본인 Gmail 추가)  
2. **사용자 인증 정보** → **+ 사용자 인증 정보 만들기** → **OAuth 클라이언트 ID**  
3. 애플리케이션 유형: **웹 애플리케이션**  
4. 아래 **두 칸을 구분**해서 넣기 (칸을 바꾸면 `올바르지 않은 출처: URI는 경로를 포함…` 오류 남):

| Console 항목 (한글/영문) | 넣을 값 | 경로(`/oauth2/…`) |
|--------------------------|---------|-------------------|
| **승인된 JavaScript 원본** / Authorized JavaScript origins | `https://cronusfarm.duckdns.org` | **넣지 않음** |
| **승인된 리디렉션 URI** / Authorized redirect URIs | `https://cronusfarm.duckdns.org/oauth2/callback` | **여기만** |

- JavaScript 원본: `https://` 만, **끝에 `/` 없음**, `/oauth2` 없음  
- 리디렉션 URI: oauth2-proxy 콜백 **전체 경로** (끝 `/` 없음)

5. **클라이언트 ID** (`….apps.googleusercontent.com`) 와 **클라이언트 보안 비밀** 복사

## 4. PC에서 Pi로 반영 (권장)

```powershell
cd D:\WorkSpace\Study\MyCode\Cursor\CronusFarm
copy deploy\env\oauth2-proxy.env.example deploy\env\oauth2-proxy.env
notepad deploy\env\oauth2-proxy.env   # CLIENT_ID, CLIENT_SECRET 만 채우기
.\scripts\pi-finish-oauth2-login.ps1
```

(`deploy\env\oauth2-proxy.env` 는 git에 올라가지 않음)

## 5. 확인

- `https://cronusfarm.duckdns.org/farm/ui/` → Google 로그인  
- 설정 화면 **Google 로그인: 동작 중**  
- 첫 로그인 → `cf_member` 자동 등록 → **관리** (`#/admin`)

## 6. Basic Auth

Google만 쓰려면 `/etc/nginx/cronusfarm-auth.conf` 를 비우고 `sudo systemctl reload nginx`.
