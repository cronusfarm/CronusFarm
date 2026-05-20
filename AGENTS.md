# CronusFarm — 에이전트(커서) 안내

이 파일은 **저장소 루트**에 두며, Cursor가 이 폴더를 워크스페이스로 열면 **자동으로 참고**할 수 있습니다(프로젝트별 에이전트 지침).

## 프로젝트 한 줄 요약

스마트팜 제어: **Arduino(UNO R4 WiFi)** 스케치(`arduino/CronusFarm/`)와 **라즈베리파이** 배포·Node-RED 플로우(`nodered/`, `scripts/`)를 한 저장소에서 관리합니다.

## Pi(ida) 접속 (고정)

- **호스트 우선순위:** LAN `192.168.60.222` → Tailscale `ida.mango-larch.ts.net` → DuckDNS `cronusfarm.duckdns.org` (`scripts/cronusfarm-network.ps1`). **로컬 개발**은 Tailscale 고정(`run-nodered-local-ui.ps1`).
- **포트(라우터 포워딩 정합):** nginx `1880`, NR `51880`~`51882`, CCTV `8080`~`8081`, MQTT `51883`, SQLite `18766`. 설정: `scripts/cronusfarm-network.json`.
- **내부 LAN(폴백):** `192.168.60.222` (ida 고정)
- **SSH:** `dooly@ida.mango-larch.ts.net` 우선(Tailscale). LAN만 쓸 때 `dooly@192.168.60.222`. 배포 스크립트는 기본으로 Tailscale SSH를 먼저 시도합니다.
- **IP/웹이 안 될 때:** PC와 Pi가 **같은 LAN 대역(예: 192.168.60.x)** 인지, 주소는 **`http://`**, Pi `ufw`/라우터 AP 격리 확인. 외부에서는 **Tailscale**만 통할 수 있음.
- **`pi-diagnose-ui.sh`가 Pi에 없으면:** 클론이 오래됐거나 스크립트가 아직 원격에 없음 → `git pull` 또는 레포 루트에서 `bash scripts/pi-install-diagnose-to-home.sh`.

## 반드시 지킬 것

1. **`arduino/CronusFarm/secrets.h`** 는 `.gitignore` 대상입니다. 예시만 수정하려면 **`secrets.h.example`** 을 고치고, 로컬 비밀은 각자 `secrets.h` 에만 둡니다.
2. 배포·업로드 흐름은 **`README.md`**(개발 PC→Pi `upcode`→USB 업로드→Node-RED·GitHub), Pi 쪽 상세는 **`docs/raspi_setup.md`**, Git·맥 이어하기·푸시 전 백업 태그는 **`docs/git_workflow.md`** 를 우선합니다. 대시보드 JSON 수정·머지·Pi 반영 절차는 **`docs/nodered_dashboard_workflow.md`**, R3/R4·2004A EXP 배선 정본은 **`docs/v07_2004a_exp_wiring.md`** 를 본다.
3. 사용자·워크스페이스 규칙: **`.cursor/rules/`** 의 `*.mdc` 파일들이 함께 적용됩니다(예: 응답 마지막 줄 형식 등).
4. **Node-RED 플로우·대시보드 JSON을 수정한 경우**, Cursor 에이전트는 우선 **`python scripts/merge_nodered_deploy.py --use-split`** 으로 `merged-deploy.json` 을 맞춘다. **UI 검증 기본값은 로컬**이다: 사용자에게 **`scripts/run-nodered-local-ui.ps1`** 로 로컬 Node-RED를 띄운 뒤 `nodered/merged-deploy.json` 을 Import·Deploy 하도록 안내한다(세부는 `docs/nodered_dashboard_workflow.md`). **Pi 반영**은 사용자가 배포를 **명시**했을 때만 `scripts/deploy-cronusfarm-pi.ps1 -ApplyNodeRed`(Arduino 업로드가 요청되지 않았으면 `-SkipArduino`)를 실행한다. Pi 배포를 시도한 경우에 한해 재시도·실패 보고를 한다.

## 어디서 “불러오나”?(맥·다른 계정)

별도 “import” 메뉴가 필요하지 않습니다. **`git clone` 으로 받은 폴더를 Cursor로 연면**, 같은 경로의 `AGENTS.md`·`.cursor/rules/`·`docs/` 가 그대로 따라옵니다.
