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
저장소 `scripts/deploy-cronusfarm-pi.ps1` 는 순서대로 **upcode(스케치 복사·컴파일·업로드)** → **`nodered/*.json` 을 Pi의 `~/CronusFarm/nodered/` 로 복사** → 선택 시 **`merged-deploy.json` 을 `POST http://127.0.0.1:1880/flows` 로 반영**합니다.
- JSON만 동기화: `deploy-cronusfarm-pi.ps1`
- Node-RED까지 자동 적용: `deploy-cronusfarm-pi.ps1 -ApplyNodeRed` (실행 중인 NR의 **전체 플로우가 교체**되므로, 다른 탭이 있으면 백업 파일 `~/.node-red/flows.cronusfarm-backup.*.json` 을 확인하세요.)

Pi에만 있을 때 수동 적용: `scripts/pi-nodered-apply-merged.sh /home/dooly/CronusFarm/nodered/merged-deploy.json`

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

