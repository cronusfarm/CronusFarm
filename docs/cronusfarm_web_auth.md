# CronusFarm 웹 접속 보호

## 1. nginx HTTP Basic Auth (권장·간단)

브라우저가 **ID/비밀번호**를 묻는 방식입니다. Google/Kakao 계정과 연동되지 않습니다.

### 동작

- `/ui/`, `/farm/ui/` 요청 시 nginx가 `401` → 브라우저 로그인 창
- 비밀번호 파일: `/etc/nginx/cronusfarm-htpasswd` (해시 저장, 평문 없음)

### 최초 설정 (Pi)

```bash
bash ~/CronusFarm/scripts/pi-nginx-set-basic-auth.sh dooly
# 비밀번호 입력 (2회)
```

### 사용자 추가

```bash
# 기존 파일에 추가 (-c 쓰면 안 됨, 덮어씀)
sudo htpasswd /etc/nginx/cronusfarm-htpasswd 새사용자
sudo systemctl reload nginx
```

### 비밀번호 변경

```bash
sudo htpasswd /etc/nginx/cronusfarm-htpasswd dooly
sudo systemctl reload nginx
```

### 사용자 삭제

```bash
sudo htpasswd -D /etc/nginx/cronusfarm-htpasswd 삭제할사용자
sudo systemctl reload nginx
```

### 해제

```bash
sudo rm -f /etc/nginx/cronusfarm-auth.conf /etc/nginx/cronusfarm-htpasswd
sudo systemctl reload nginx
```

`deploy/nginx/cronusfarm-auth.conf` 가 비어 있으면 로그인 없음.

---

## 2. oauth2-proxy + Google (권장·회원 가입)

**상세 절차:** [cronusfarm_google_login_setup.md](cronusfarm_google_login_setup.md)

Pi에서:

```bash
bash ~/CronusFarm/scripts/pi-install-oauth2-proxy-google.sh
sudo nano /etc/cronusfarm/oauth2-proxy.env   # CLIENT_ID, CLIENT_SECRET
sudo systemctl restart cronusfarm-oauth2-proxy nginx
```

- **Redirect URI** (Google Console): `https://ida.mango-larch.ts.net/oauth2/callback` (HTTPS 필수 — Tailscale Serve/Funnel 또는 Let's Encrypt)
- 로그인 후 nginx가 `X-Forwarded-Email` 을 브리지·`/farm/ui/` 로 전달 → `GET /api/admin/me` 에서 회원 자동 등록
- **관리 SPA**: `http://<호스트>/farm/ui/#/admin`

## 3. oauth2-proxy + Google (상세·공수)

| 항목 | 내용 |
|------|------|
| **난이도** | Basic Auth보다 **훨씬 큼** (반나절~1일+ 튜닝) |
| **필수 준비** | Google Cloud OAuth 클라이언트 ID/Secret, **HTTPS 공개 URL**(또는 Tailscale Funnel), redirect URI 등록 |
| **Pi 구성** | `oauth2-proxy` 바이너리/systemd, nginx `auth_request` 또는 프록시 앞단 |
| **Kakao** | 공식 지원 약함 → 별도 OIDC 설정·문서 따라야 함 |

### 대략 작업 순서

1. `https://cronusfarm.duckdns.org` 등 **고정 HTTPS** (Let's Encrypt)
2. Google Cloud Console → OAuth 동의 화면 + **웹 클라이언트** 생성
3. Redirect URI: `https://<도메인>/oauth2/callback`
4. Pi에 oauth2-proxy 설치·환경변수(`OAUTH2_PROXY_CLIENT_ID` 등)
5. nginx에서 `/farm/ui/`, `/ui/` 를 oauth2-proxy 경유로 프록시

**Tailscale vs 공개:** nginx `map $host` 로 **DuckDNS 호스트만** `auth_request` 합니다. `ida.mango-larch.ts.net` 등 `*.ts.net` 은 Google 로그인 없이 접속합니다.

Tailscale만 쓰는 환경에서는 Google OAuth 없이도 됩니다. 공개 DuckDNS를 열 때만 oauth2-proxy를 켜세요.
