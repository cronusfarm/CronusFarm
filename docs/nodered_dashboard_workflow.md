# Node-RED 대시보드(UI) 개발·반영 흐름

CronusFarm 모니터/설정 탭의 **Dashboard(구 node-red-dashboard)** UI는 저장소의 JSON으로 관리한다. **기본 개발환경은 Windows PC 로컬 Node-RED**이며, Pi 배포는 반영 확인 후 별도로 한다.

## 편집하는 파일

| 용도 | 경로 |
|------|------|
| 대시보드 전용(넓은 `ui_template`·CSS) | `nodered/flows_cronusfarm_dashboard.json` |
| MQTT/브로커 등과 합친 배포본 생성 입력 | `nodered/CronusFarm_NodeRED_flow.json` 등(머지 스크립트가 참조) |

레이아웃·타일 문구·`tele(요약)` / `tele(raw)` 박스 등은 대부분 **`flows_cronusfarm_dashboard.json`** 안의 `ui_template` 노드 `format` 필드다.

## 로컬 개발환경(Windows / 저장소 루트) — 기본

1. **`nodered/flows_cronusfarm_dashboard.json`** 등 분할 소스 수정.
2. 대시보드 변경을 export 쪽과 맞추기:
   ```powershell
   python scripts/sync_nodered_dashboard_into_export.py
   ```
3. 통합 JSON 재생성:
   ```powershell
   python scripts/merge_nodered_deploy.py --use-split
   ```
   (단일 내보내기만 다룰 때는 `AGENTS.md`·스크립트 도움말에 따라 인자 없이 실행해도 됨.)
4. **로컬에서 UI 확인**:
   ```powershell
   .\scripts\run-nodered-local-ui.ps1
   ```
   - 첫 실행 전 `userDir`(기본 `.\.nodered-local`)에 스크립트가 안내하는 버전으로 `npm install` 이 필요할 수 있다.
   - 브라우저: `http://127.0.0.1:1881/ui/` (포트는 스크립트 기본값, `-Port` 로 변경 가능).
   - 편집기(`http://127.0.0.1:1881/`)에서 **메뉴 → Import** 로 **`nodered/merged-deploy.json`** 을 가져온 뒤 **Deploy** 한다.

로컬은 MQTT 하드웨어가 없어도 대시보드 레이아웃·바인딩 구조 검증에는 쓸 수 있다(데이터 소스 노드는 빈 값·연결 오류가 날 수 있음).

## Pi(운영) 반영 — 필요할 때만

머지·로컬에서 만족한 뒤 장비에 올릴 때:

- **권장(개발 PC에서)**: `scripts/deploy-cronusfarm-pi.ps1 -ApplyNodeRed` (Arduino 생략 시 `-SkipArduino`).
- Pi 쉘만 있을 때: `scripts/pi-nodered-apply-merged.sh` 로 `merged-deploy.json` 적용.

## 하드웨어 핀·라벨을 UI에 맞출 때

- **R4 릴레이/LED/펌프/팬** 핀 정의는 `arduino/CronusFarm/CronusFarm.ino` 및 **`docs/v07_2004a_exp_wiring.md`** 를 정본으로 한다.
- 대시보드에 `(R4-Dx)` 같은 표기를 바꿀 때는 **펌웨어 핀과 숫자가 어긋나지 않게** JSON만 수정하지 말고, 위 문서·`.ino`와 **한 번에 맞춘다**.

## Pi에서 확인

- Node-RED 재시작이 필요하면: `sudo systemctl restart nodered.service`
- 브라우저에서 대시보드 탭 **강력 새로고침**(캐시 무시).

## 관련 문서

- Pi 전체: `docs/raspi_setup.md`
- Git: `docs/git_workflow.md`
- 에이전트 기본 동작: 저장소 루트 `AGENTS.md`, `.cursor/rules/pi-nodered-deploy.mdc`
