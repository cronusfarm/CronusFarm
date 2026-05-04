# CronusFarm 스케줄 변경하기 — 구조 설계 (초안)

## 목표

- NRDB2 설정 화면에서 **채널별** 시간대 기준 ON/OFF 규칙을 **조회·편집**한다.
- **SQLite를 마스터(정합)** 로 두고, 변경분은 **MQTT `cmd`** 로 Arduino에 전달해 펌웨어 스케줄러와 동기화한다.

## 데이터 모델 (제안)

| 항목 | 설명 |
|------|------|
| `device_id` | 예: `cronusfarm-01` |
| `channel` | `led_a1`, `pump_b2`, … (토픽 키와 동일) |
| `rule_id` | 규칙 UUID 또는 정수 |
| `dow_mask` | 요일 비트마스크 (7비트). UI·펌웨어 통일: **월=1, 화=2, 수=4, 목=8, 금=16, 토=32, 일=64** — 필요한 요일 값을 더함(전 요일이면 127). |
| `on_time` / `off_time` | 하루 내 시각 (분 단위 또는 `HH:MM`) |
| `enabled` | 규칙 활성 |
| `updated_at` | 수정 시각 |
| `version` | 배포용 증가 버전 |

원하면 **여러 구간**(예: 06:00–08:00 ON, 12:00–12:15 ON)을 `schedule_rules` 행으로 분리하고, UI에서는 채널별 리스트로 표시한다.

## 동기화 흐름

1. 사용자가 UI에서 저장 → Node-RED가 SQLite에 트랜잭션 저장, `version++`.
2. 동일 메시지 또는 후속 메시지로 `cronusfarm/<DEVICE_ID>/cmd` 에 페이로드 예:
   - `SCHED_JSON=<urlencoded 또는 축약 KV>` 또는 별도 토픽 `.../cmd/schedule`.
3. 펌웨어는 수신 후 **내부 RAM + EEPROM/Flash** 에 반영하고, 다음 `tele` 에 `sch_ver=<n>` 또는 해시를 실어 보낸다.
4. Node-RED는 DB의 `version` 과 `tele` 의 버전을 비교해 UI에 **동기화됨 / 대기 중 / 불일치** 표시.

## Node-RED 역할

- **HTTP in** (로컬만 또는 인증): 스케줄 CRUD → SQLite (`cronusfarm_sqlite_bridge` 또는 확장).
- **MQTT out**: 저장 후 `cmd` 발행.
- **MQTT in / tele 파싱**: 적용 확인 후 플로우 컨텍스트 또는 DB 플래그 갱신.

## 펌웨어 (Arduino)

- 현재 ROM에 박힌 스케줄 테이블을 **런타임 덮어쓰기 가능한 구조**로 확장하거나, 수신 JSON을 파싱해 **동일 자료구조**로 채운다.
- EEPROM 크기·마이그레이션 버전 필드 권장.

## 구현 진행 상황

- SQLite `schedule_rule`: **시간대(`rule_kind=window`)** 는 하루 내 `on_min`/`off_min`(분), **주기(`rule_kind=cycle`)** 는 `on_sec`/`off_sec`(반복 길이, 초).
- 브리지 `GET/PUT /api/schedule`. NRDB2 UI는 브라우저에서 **직접 `:18766` 호출 대신** Node-RED와 동일 출처의 **`/farm/cronusfarm-sqlite/api/schedule`** 로 요청(플로우에 HTTP 프록시 노드)해 `Failed to fetch`·혼합 콘텐츠 이슈를 줄임.
- 스케줄 저장 후 장치 통지(선택): `CRONUSFARM_SCHEDULE_MQTT=1` + `mosquitto_pub` 시 `cmd` 로 `SCHED_JSON=…` (rules에 `rule_kind`, `on_sec`/`off_sec` 포함).

## 다음 구현 단계

1. 펌웨어: `cmd` 에서 `SCHED_JSON` 파싱 → 내부 스케줄 테이블 반영, EEPROM/Flash 버전 필드.
2. `tele` 에 `sch_ver`(또는 해시) 포함 → Node-RED/SQLite 메타와 비교해 UI에 동기화 상태 표시.
3. (선택) 스케줄 버전을 SQLite에 두고 `sch_ver` 단조 증가.

본 문서는 요구사항 확정에 따라 갱신한다.
