## CronusFarm (스마트팜 제어 패널)

이 폴더는 Windows(커서/VS Code)에서 작업하는 **아두이노 스케치**와 **라즈베리파이 업로드 자동화**를 함께 관리하기 위한 프로젝트입니다.

### 폴더 구조
- `arduino/` : 아두이노 스케치(UNO R4 WiFi)
- `scripts/` : 라즈베리파이(Tailscale `ida.mango-larch.ts.net`)로 업로드/배포 자동화 스크립트
- `.vscode/` : 작업(Task) 설정

### 빠른 시작(개발 PC → 라즈베리파이에서 업로드 실행)
1. **라즈베리파이**에 `arduino-cli`가 설치되어 있어야 합니다(보드는 Pi USB에 연결).
2. **Windows**에서 SSH/SCP 가능(`ssh`/`scp` 명령). `deploy-cronusfarm-pi.ps1`·`upcode.ps1` 등은 **같은 LAN이면 `192.168.1.22`(ida) 우선**, 아니면 **`ida.mango-larch.ts.net`** 으로 접속합니다. 호스트를 고정하려면 `-PiHost` 로 지정하세요. 계정은 기본 `dooly` 또는 `-PiUser` 로 맞출 것.
3. **커서/VS Code**에서 Task **`upcode (copy->compile->upload Pi)`** 실행 → 스케치 폴더 전체가 Pi로 복사된 뒤, Pi에서 `arduino-cli core`·`lib` 준비(이미 있으면 스킵) → **컴파일·업로드**까지 한 번에 수행됩니다.
4. **수동 옵션(파워셸):** `.\scripts\upcode.ps1 -AutoPort` — `ttyACM` 포트 자동 선택. 시리얼 점유 시 `.\scripts\upcode.ps1 -StopNodeRedDuringUpload` (sudo 필요할 수 있음). **Thalia의 `arduino/CronusFarm/` 전체(`.ino`·`secrets.h`)를 ida로 복사한 뒤 업로드**합니다. ida SSH에서만 `upcode` 하면 Thalia와 자동 동기화되지 않습니다.
5. **Pi에만 있을 때:** `upcode` 또는 `upcod` 별칭(자세히는 `docs/raspi_setup.md` 3·4절). 수동 빌드: `chmod +x scripts/pi-arduino-build.sh` 후 `FQBN=arduino:renesas_uno:unor4wifi ./scripts/pi-arduino-build.sh /home/dooly/CronusFarm/arduino/CronusFarm`.

#### 한 번에 배포(Arduino 업로드 + Node-RED 플로우)
- **JSON만 Pi에 복사**(수동 Import 가능):  
  `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\deploy-cronusfarm-pi.ps1`  
  또는 Task **`deploy Pi: arduino + nodered JSON 동기화`**
- **저장소 플로우를 Node-RED에 바로 반영**(기존 `~/.node-red/flows.json` 백업 후 `POST /flows`로 **전체 교체**):  
  `.\scripts\deploy-cronusfarm-pi.ps1 -ApplyNodeRed`  
  또는 Task **`deploy Pi: 전체(Arduino + Node-RED POST 적용)`**  
  - Node-RED에 **관리자 로그인**이 켜져 있으면 `curl`이 실패할 수 있음 → UI에서 Import 하거나 Pi의 `settings.js`에서 임시로 비활성화 후 재시도.

### MQTT 전환(추천: Node-RED 유지 + 업로드 충돌 제거)
Serial(USB)로 Node-RED를 붙이면 `/dev/ttyACM0` 점유로 업로드가 막힐 수 있습니다.
이를 피하려면 **Node-RED ↔ Arduino 런타임 통신을 MQTT(WiFi)** 로 전환하고, USB는 업로드/디버그 용도로만 사용하세요.

#### Arduino 설정
1. `arduino/CronusFarm/secrets.h.example`을 복사해서 `arduino/CronusFarm/secrets.h`를 만들고 값 채우기
2. 스케치: `arduino/CronusFarm/CronusFarm.ino` (MQTT 제어 기본 스케치)

#### Node-RED 예시 플로우
- `nodered/flows_cronusfarm_mqtt.json` 를 Node-RED에서 Import 하면 됩니다.
- Pi는 `iwgetid -r` 결과를 **5분마다** `cronusfarm/pi/wifi_ssid`(retain)로 발행합니다. 아두이노 `secrets.h`의 `WIFI_AP_SSIDS` **맨 앞**에 Pi와 동일 SSID·비밀번호를 두면 WiFi가 그 AP를 먼저 시도합니다.
- 기본 DEVICE_ID는 `cronusfarm-01` 입니다(Arduino의 `secrets.h`와 일치시켜야 함).

#### Node-RED 대시보드(추천)
- `nodered/flows_cronusfarm_dashboard.json` 를 Import 하면 됩니다.
- 개발·배포 순서도는 **`nodered/flows_cronusfarm_devflow_flow.json`** 플로우(에디터 탭 `CronusFarm 개발흐름`)의 `ui_template`이 대시보드 탭 **`CronusFarm-개발흐름`** 에 그립니다. `deploy-cronusfarm-pi.ps1` 병합에 포함됩니다.
- 포함 기능
  - Pi 상태: 부팅(uptime), WiFi SSID, IP, Node-RED/Mosquitto 서비스 상태
  - Arduino 상태: status/tele 수신 시각 기반 연결 상태(LED), tele(raw) 표시
  - 모니터: A Bed(LED A1/A2, Pump A1/A2) / B Bed(LED B1, Pump B1/B2) 상태 표시 + 수동 토글
  - 설정: 채널별 AUTO + 펌프별 ON/OFF(초) 변경 → `cronusfarm/<DEVICE_ID>/cmd` 발행

#### Mosquitto(라즈베리파이) 개요
- 브로커 호스트명(Tailscale MagicDNS): `ida.mango-larch.ts.net` — LAN IP 대신 사용해 WiFi AP가 바뀌어도 동일 주소로 연결
- 포트: `1883`

### Git 협업(Thalia / 맥 공용 소스)

원격 저장소를 정본으로 쓰고, 맥·다른 Cursor 계정에서는 **같은 저장소를 클론**해 작업합니다. `secrets.h` 는 Git에 올리지 않습니다(`secrets.h.example` 참고). 절차·백업 정리는 **`docs/git_workflow.md`** 를 봅니다.


