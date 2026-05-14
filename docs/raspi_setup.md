## 라즈베리파이 설정 요약 (MQTT + 업로드)

Pi LAN IP는 WiFi AP마다 달라질 수 있으므로, **SSH·MQTT·Arduino `MQTT_HOST`** 는 Tailscale MagicDNS 호스트 **`ida.mango-larch.ts.net`** 로 통일합니다.

### 1) Mosquitto 설치/실행
```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients
sudo systemctl enable --now mosquitto
```

동작 확인:
```bash
mosquitto_sub -h localhost -t 'cronusfarm/#' -v
```

### 2) arduino-cli 준비(보드 코어 포함)
아두이노가 **라즈베리파이 USB**에 꽂혀 있으면, **업로드·컴파일은 Pi에서** 하는 것이 맞습니다(윈도우 PC의 COM 포트가 아님).

```bash
arduino-cli version
arduino-cli core update-index
arduino-cli core install arduino:renesas_uno
arduino-cli lib install "ArduinoMqttClient"
arduino-cli board list
```

- `Arduino_LED_Matrix` 등 일부 라이브러리는 코어에 포함되어 별도 설치가 없을 수 있습니다.
- 스케치 폴더에 `secrets.h`가 있어야 합니다(`secrets.h.example` 참고).

### 3) Thalia vs ida: `upcode`가 하는 일(먼저 읽기)

| 어디서 실행 | 명령 | 하는 일 |
|-------------|------|---------|
| **Thalia (Windows)** | PowerShell: `.\scripts\upcode.ps1` (또는 Cursor Task **upcode**) | **Thalia의** `D:\WorkSpace\Study\MyCode\Cursor\CronusFarm\arduino\CronusFarm\` 안의 **`CronusFarm.ino`, `secrets.h` 포함 전체**를 **ida의** `~/CronusFarm/arduino/CronusFarm/` 로 **복사(scp)** 한 뒤, **ida에서** `arduino-cli`로 컴파일·아두이노(USB) 업로드 |
| **ida (SSH 로그인)** | `upcode` 또는 `upcod` (별칭) | **이미 ida 디스크에 있는** `~/CronusFarm/arduino/CronusFarm/` 만 컴파일·업로드. **Thalia 파일을 자동으로 가져오지 않음** |

정리: **Thalia에서 짠·고친 `secrets.h` / `.ino`를 보드에 반영하려면** Thalia에서 `upcode.ps1` 을 실행해야 합니다. ida에서만 `upcode` 하면 **로컬(ida)에 복사된 예전 `secrets.h`** 로 올라가 WiFi 목록이 안 맞을 수 있습니다.

### 4) 컴파일·업로드(예: 저장소 클론 경로)
**한 번에(권장):** 저장소의 `scripts/pi-arduino-build.sh` 를 Pi에 두고 실행합니다(core·lib·compile·upload 포함).

Windows 의 `upcode.ps1` 과 같은 일을 Pi에서 하려면 **`upcode.sh`** 를 씁니다. 셸 별칭으로 `upcode` / `upcod` 가 잡혀 있습니다.
```bash
chmod +x ~/CronusFarm/scripts/pi-arduino-build.sh ~/CronusFarm/scripts/upcode.sh
~/CronusFarm/scripts/upcode.sh
# 포트 지정: ~/CronusFarm/scripts/upcode.sh /dev/ttyACM0
```

편하게 쓰려면 `~/.bashrc` 에 **아래 두 줄**(또는 `pi-repair-upcode.sh` 가 넣어 주는 블록)만 유지하면 됩니다:
```bash
alias upcode='bash $HOME/CronusFarm/scripts/upcode.sh'
alias upcod='bash $HOME/CronusFarm/scripts/upcode.sh'
```
(`upcod` 는 오타 대비용으로 `upcode` 와 동일합니다.)

예전에 `MyProject` 를 가리키던 `alias upcode=...` 가 남아 있으면 **틀린 경로**입니다. 아래로 정리한 뒤 위를 다시 넣으세요.
```bash
sed -i.bak '/^[[:space:]]*alias upcode=/d' ~/.bashrc
sed -i.bak '/^[[:space:]]*alias upcod=/d' ~/.bashrc
echo "alias upcode='bash $HOME/CronusFarm/scripts/upcode.sh'" >> ~/.bashrc
echo "alias upcod='bash $HOME/CronusFarm/scripts/upcode.sh'" >> ~/.bashrc
source ~/.bashrc
```
Thalia에서 자동 정리: `powershell -File .\\scripts\\pi-install-upcode-alias.ps1`

`upcode` 가 아예 안 될 때(`.bashrc` 문법 깨짐·alias 손상) **ida에서**:
```bash
bash ~/CronusFarm/scripts/pi-repair-upcode.sh
source ~/.bashrc
type upcode
```

이후 터미널에서 `upcode` 또는 `upcode /dev/ttyACM0` 로 실행합니다. 실제 업로드 스케치는 **`~/CronusFarm/arduino/CronusFarm/`** (`CronusFarm.ino` 포함) 입니다.

직접 빌드 스크립트만 호출할 때:
```bash
chmod +x ~/CronusFarm/scripts/pi-arduino-build.sh
FQBN=arduino:renesas_uno:unor4wifi ~/CronusFarm/scripts/pi-arduino-build.sh ~/CronusFarm/arduino/CronusFarm
# 두 번째 인자 생략 시 ttyACM* 자동 탐지, 명시 시: .../CronusFarm /dev/ttyACM0
```

**수동으로 나누어:**
```bash
cd ~/CronusFarm/arduino/CronusFarm   # 실제 경로에 맞출 것
arduino-cli compile --fqbn arduino:renesas_uno:unor4wifi .
sudo arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:renesas_uno:unor4wifi .
```

- 포트는 `arduino-cli board list`로 확인합니다. UNO R4 WiFi는 보통 **`/dev/ttyACM0`** 입니다.
- 업로드 실패 시: **시리얼 모니터·`mosquitto_sub` 등이 같은 포트를 쓰고 있지 않은지** 확인하고, USB 재연결 후 다시 시도합니다.
- `Permission denied`가 나오면 일시적으로 `sudo`로 업로드하거나, 사용자를 `dialout` 그룹에 넣습니다:  
  `sudo usermod -aG dialout $USER` 후 재로그인.

### 5) Node-RED는 MQTT로 연결
Serial(USB) 대신 MQTT 노드를 사용하면 업로드와 포트 점유 충돌이 사라집니다.

### 6) 개발 PC에서 SSH/업로드(Windows → Pi)
`scripts/upcode.ps1` 기본 Pi 호스트는 **`ida.mango-larch.ts.net`** 입니다. PC에 Tailscale 클라이언트가 있고 같은 tailnet이면 `ssh dooly@ida.mango-larch.ts.net` 로 접속됩니다.

### 7) 원클릭 배포(Windows → Pi: Arduino + Node-RED)
저장소 `scripts/deploy-cronusfarm-pi.ps1` 는 순서대로 **upcode(스케치 복사·컴파일·업로드)** → **`nodered/*.json` 을 Pi의 `~/CronusFarm/nodered/` 로 복사** → **`deploy/nginx/cronusfarm-nodered.conf` 를 Pi에 두고 가능하면 `nginx reload`** → 선택 시 **`merged-deploy.json` 을 Admin API `POST …/<adminRoot>/flows` 로 반영**합니다(nginx가 1880을 쓰는 멀티플렉스면 스크립트가 **Node-RED 실제 포트(예: 1882)** 로 직접 POST 해 502를 피합니다).

추가로, 더 짧게 쓰려면 파이썬 래퍼를 사용할 수 있습니다:

```powershell
python .\scripts\deploy_all.py --apply-nodered --use-split-flows
```

- Arduino 업로드만 생략: `python .\scripts\deploy_all.py --apply-nodered --use-split-flows --skip-arduino`
- Node-RED 적용 생략(Arduino만): `python .\scripts\deploy_all.py`
- Arduino 포트 자동탐지를 끄고 싶을 때(비권장): `python .\scripts\deploy_all.py --apply-nodered --use-split-flows --no-auto-port`
- JSON만 동기화: `deploy-cronusfarm-pi.ps1`
- Node-RED까지 자동 적용: `deploy-cronusfarm-pi.ps1 -ApplyNodeRed` (실행 중인 NR의 **전체 플로우가 교체**되므로, 다른 탭이 있으면 백업 파일 `~/.node-red/flows.cronusfarm-backup.*.json` 을 확인하세요.)  
  - **`http://<Pi>:1880/nrdb2`**(Dashboard 2·개발환경)는 **`@flowfuse/node-red-dashboard`** 패키지가 있어야 열립니다. 동일 스크립트가 `pi-nodered-install-dashboard2.sh` 로 없을 때 설치를 시도합니다. 모니터/설정만 보려면 **`/ui`** 를 쓰면 됩니다.

Pi에만 있을 때 수동 적용: `scripts/pi-nodered-apply-merged.sh /home/dooly/CronusFarm/nodered/merged-deploy.json`  
nginx만 갱신: `bash ~/CronusFarm/scripts/pi-nginx-apply-cronusfarm.sh`

### 8) Samba 공유 `[MyCode]` 를 CronusFarm 과 맞추기
**자동 적용(개발 PC → ida):** `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\apply-ida-samba-mycode.ps1`  
(Pi에 `scripts/pi-apply-samba-mycode-cronusfarm.sh` 를 올린 뒤 `sudo bash` 로 `[MyCode]` 의 `path` 만 바꾸고 `testparm` 검증·`smbd` 재시작합니다.)

Windows UNC `\\ida.mango-larch.ts.net\MyCode` 가 **저장소 루트**와 같아지도록 Pi의 `/etc/samba/smb.conf` 에서 해당 공유를 다음처럼 둡니다.

```ini
[MyCode]
   path = /home/dooly/CronusFarm
   browseable = yes
   read only = no
   valid users = dooly
```

- **기존** `path = /home/dooly/MyProject/code` 를 쓰던 경우: `MyProject/code` 에만 있던 파일이 필요하면 **먼저 백업·이동**한 뒤 `path` 를 바꿉니다.
- 적용 후 Samba 재시작: `sudo systemctl restart smbd nmbd` (배포판에 따라 서비스 이름은 `smbd` 만일 수 있음).
- UNC로는 예: `\\ida.mango-larch.ts.net\MyCode\arduino\CronusFarm\` 가 스케치 폴더입니다(`upcode.ps1` 기본 원격 경로와 동일 트리).

### 9) SQLite 기록 브리지 (선택·권장)

Node-RED가 MQTT `tele` / `cmd` / `status`를 수집해 SQLite에 넣으려면 **로컬 HTTP 브리지**를 띄웩니다.

**먼저** 개발 PC에서 `.\scripts\deploy-cronusfarm-pi.ps1 -SkipArduino` 를 한 번 실행해 Pi의 `~/CronusFarm/scripts/` 에 `init_cronusfarm_sqlite.py`, `cronusfarm_sqlite_bridge.py`, `scripts/sql/cronusfarm_record_v1.sql`, `deploy/systemd/...` 가 올라가 있는지 확인합니다. (예전 Pi 폴더에는 이 파일들이 없을 수 있습니다.)

```bash
python3 ~/CronusFarm/scripts/init_cronusfarm_sqlite.py ~/.node-red/cronusfarm.sqlite
sudo cp ~/CronusFarm/deploy/systemd/cronusfarm-sqlite-bridge.service /etc/systemd/system/
# 홈만 바꿉니다. 저장소 폴더명은 대소문자 포함 **CronusFarm** 과 동일해야 합니다.
sudo sed -i "s|/home/pi/|$HOME/|g" /etc/systemd/system/cronusfarm-sqlite-bridge.service
sudo systemctl daemon-reload
sudo systemctl enable --now cronusfarm-sqlite-bridge
curl -s http://127.0.0.1:18766/health
```

- 스키마·테이블: `docs/cronusfarm_sqlite_schema.md`
- 브리지 없으면 Node-RED HTTP 노드가 실패할 수 있어, 테스트 시 `CRONUSFARM_SQLITE_DISABLE=1`(Node-RED 환경변수)로 끌 수 있습니다.
- `systemctl`에 `ExecStart=.../cronusfarm/scripts`(소문자)로 나오면 경로 오류입니다. 아래로 고친 뒤 `daemon-reload` 하세요.  
  `sudo sed -i 's|/cronusfarm/scripts|/CronusFarm/scripts|g' /etc/systemd/system/cronusfarm-sqlite-bridge.service`

**쉬운 자가진단(KV·브리지·DB 한 번에)** — Pi에서:
```bash
bash ~/CronusFarm/scripts/pi-check-sqlite-kv.sh
```
(`deploy-cronusfarm-pi.ps1` 로 올리면 스크립트가 같이 동기화됩니다. 없으면 저장소에서 `scripts/pi-check-sqlite-kv.sh` 를 복사해 실행.)

### 10) Edge AI(준비): IP 카메라 + LLM(Ollama) + (추후) Hailo

현재 단계(요구사항):
- 카메라는 **기존 IP 카메라(RTSP)** 를 사용하고, 추후 **CSI Pi 카메라**로 전환 가능하도록 구성
- Vision(탐지)은 추론 서비스가 담당하고, Node-RED는 **결과(JSON) 저장/알림/대시보드**만 담당
- 오버레이 영상(박스 그려진 스트림)은 **대시보드에 직접 임베드하지 않고 “별도 링크”**로만 제공(UX/부하 최소화)

#### 10-1) Ollama 설치(LLM 런타임)
```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
ollama --version
```

모델(예: Gemma 2B) 다운로드:
```bash
ollama pull gemma:2b
# 또는 모델명이 다를 때(환경에 따라): ollama pull gemma2:2b
```

#### 10-2) Node-RED 플로우(텔레그램 + SQLite + Ollama)
- 권장 노드:
  - `node-red-contrib-telegrambot`
  - `node-red-node-sqlite`
- 설치(일반적으로 `~/.node-red`에서):
```bash
cd ~/.node-red
npm i node-red-contrib-telegrambot node-red-node-sqlite
sudo systemctl restart nodered.service
```

**텔레그램 전송 테스트(HTTP, 토큰은 플로우에 넣지 않음)**  
저장소 플로우에 `GET /farm/cronusfarm/telegram-ping` 가 있으면, Pi에서 Node-RED 서비스 환경변수만 넣고 브라우저·curl 로 확인할 수 있습니다.

```bash
# 예: systemd drop-in 또는 서비스 유닛 Environment=
# CRONUSFARM_TELEGRAM_BOT_TOKEN=...
# CRONUSFARM_TELEGRAM_CHAT_ID=...
curl -sS "http://127.0.0.1:1880/farm/cronusfarm/telegram-ping?text=테스트"
```

환경변수가 비어 있으면 HTTP 500 과 JSON 오류 본문을 반환합니다.

**systemd로 환경변수 넣기(권장)**  
배포 시 `deploy-cronusfarm-pi.ps1 -ApplyNodeRed` 가 `pi-install-nodered-telegram-env.sh` 를 호출해 drop-in을 깔고, 없을 때만 `/etc/cronusfarm/nodered-telegram.env` 를 만듭니다. 토큰·chat_id 는 Pi에서만 편집합니다: `sudo nano /etc/cronusfarm/nodered-telegram.env` 후 `sudo systemctl restart nodered.service`.

**봇 자동 응답(환영·키워드 안내)**  
`getUpdates` 짧은 폴링(약 8초)으로 `/start`·`/help` 는 환영 안내만 보내고, **그 외 텍스트는 바로 키워드 매칭 답변**을 보냅니다(대화 단계 상태를 저장하지 않아 배포·재시작 후에도 동작이 단순합니다). 토큰만 있으면 되며 **웹훅을 걸면 폴링이 비게 될 수 있어** 자동응답 시에는 웹훅을 쓰지 않는 편이 안전합니다.

**nginx 404 인 경우(로컬 curl 도 `<center>nginx</center>` HTML 이면 동일)**  
`1880` 이 **nginx** 이고 `/farm/` 이 Node-RED 업스트림으로 안 넘어가서입니다.

1. Node-RED HTTP 의 **실제 포트** 확인: `ss -tlnp | grep -iE 'node|188'`, `grep uiPort ~/.node-red/settings.js`
2. 해당 포트로 직접 호출해 동작 여부 확인: `curl -sS "http://127.0.0.1:<NR포트>/farm/cronusfarm/telegram-ping"`
3. nginx `server` 블록에 **`location ^~ /farm/`** → `proxy_pass http://127.0.0.1:<NR포트>;` 추가. 예시는 저장소 `scripts/pi-nginx-farm-location.snippet.conf` 참고.
4. `sudo nginx -t && sudo systemctl reload nginx` 후 다시 `1880` 으로 테스트.

**nginx 502 (대개 `POST /admin/flows`·대시보드 배포)**  
**로컬 `curl 127.0.0.1:1880/ui/` 가 `Server: nginx` + 502 인 경우:** nginx 가 1880 을 잡고 Node-RED 는 **1882** 등 업스트림에서 떠 있어야 하는데 NR 이 1880 으로만 떠 있거나 NR 이 꺼져 있으면 502 가 납니다. Pi에서 `bash ~/CronusFarm/scripts/pi-nodered-ensure-upstream-for-nginx.sh` (sudo 비번이면 drop-in 적용·`nodered` 재시작) 또는 멀티플렉스 전체: `scripts/pi-nodered-multiplex-v05-v07.sh` 참고.

본문 크기 제한·업스트림 응답 지연으로 프록시가 끊기면 502가 납니다. 저장소 `deploy/nginx/cronusfarm-nodered.conf`( `client_max_body_size`·긴 `proxy_*_timeout` 등)를 Pi에 반영: `bash ~/CronusFarm/scripts/pi-nginx-apply-cronusfarm.sh` 또는 Windows에서 `deploy-cronusfarm-pi.ps1` 한 번 실행. `pi-nodered-apply-merged.sh` 는 기본 **`~/.node-red/flows.json` 복사 + `nodered` 재시작**만 하며(Admin `POST` 생략·502 회피), 예전처럼 API만 쓰려면 Pi에서 `CRONUSFARM_NR_DEPLOY=api` 를 붙여 실행합니다.

#### 10-3) Hailo (추후 장착 시)
- Hailo AI Kit 장착 후에는 Hailo 제공 런타임/예제(TAPPAS/Model Zoo 등)를 설치해야 합니다.
- 프로젝트 권장 구조:
  - (별도 서비스) **RTSP → Hailo 추론 → 결과 JSON(MQTT/HTTP)**
  - (Node-RED) JSON 수집 → SQLite 저장 + 알림/요약(LLM) + 오버레이 링크 제공

