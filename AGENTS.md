# CronusFarm — 에이전트(커서) 안내

이 파일은 **저장소 루트**에 두며, Cursor가 이 폴더를 워크스페이스로 열면 **자동으로 참고**할 수 있습니다(프로젝트별 에이전트 지침).

## 프로젝트 한 줄 요약

스마트팜 제어: **Arduino(UNO R4 WiFi)** 스케치(`arduino/CronusFarm/`)와 **라즈베리파이** 배포·Node-RED 플로우(`nodered/`, `scripts/`)를 한 저장소에서 관리합니다.

## 반드시 지킬 것

1. **`arduino/CronusFarm/secrets.h`** 는 `.gitignore` 대상입니다. 예시만 수정하려면 **`secrets.h.example`** 을 고치고, 로컬 비밀은 각자 `secrets.h` 에만 둡니다.
2. 배포·업로드 흐름은 **`README.md`**(개발 PC→Pi `upcode`→USB 업로드→Node-RED·GitHub), Pi 쪽 상세는 **`docs/raspi_setup.md`**, Git·맥 이어하기·푸시 전 백업 태그는 **`docs/git_workflow.md`** 를 우선합니다.
3. 사용자·워크스페이스 규칙: **`.cursor/rules/`** 의 `*.mdc` 파일들이 함께 적용됩니다(예: 응답 마지막 줄 형식 등).

## 어디서 “불러오나”?(맥·다른 계정)

별도 “import” 메뉴가 필요하지 않습니다. **`git clone` 으로 받은 폴더를 Cursor로 연면**, 같은 경로의 `AGENTS.md`·`.cursor/rules/`·`docs/` 가 그대로 따라옵니다.
