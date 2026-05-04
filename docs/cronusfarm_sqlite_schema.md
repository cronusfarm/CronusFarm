# CronusFarm SQLite 기록 스키마 (v1 확정)

- **파일**: `scripts/sql/cronusfarm_record_v1.sql`
- **초기화**: `python scripts/init_cronusfarm_sqlite.py [경로]`
- **HTTP 수집**: `scripts/cronusfarm_sqlite_bridge.py` (기본 `http://127.0.0.1:18766`)
- **Node-RED**: `flows_cronusfarm_mqtt.json` 에서 tele/cmd/status → 브리지 POST

## 테이블 요약

| 테이블 | 용도 |
|--------|------|
| `schema_version` | 마이그레이션 버전 |
| `device` | 장치 ID 마스터 |
| `tele_sample` | MQTT `tele` 원문·토픽·시각 |
| `tele_channel_fact` | S/A/T 파싱 결과(채널별 한 줄) |
| `mqtt_cmd_log` | MQTT `cmd` 발행 기록 |
| `mqtt_status_log` | MQTT `status`(online/offline) |
| `pump_guard_event` | `G:` 구간의 mx/mf 등 이벤트 |
| `settings_kv` | 관제 UI·규칙용 키-값 |
| `manual_switch_event` | 수동 전환 이력(추후 규칙 엔진 연동) |
| `schedule_profile` | 스케줄 JSON (추후) |
| `alert_rule` | 알림 규칙 JSON (추후) |
| `sensor_reading` | pH·EC·온습도 등 센서 스냅샷(HTTP/ETL 적재용) |

## 환경 변수 (Pi)

| 변수 | 의미 |
|------|------|
| `CRONUSFARM_SQLITE_PATH` | DB 경로 |
| `CRONUSFARM_SQLITE_BRIDGE_URL` | Node-RED→브리지 URL (기본 `http://127.0.0.1:18766`) |
| `CRONUSFARM_SQLITE_DISABLE` | `1` 이면 MQTT→SQLite 비활성 |
| `CRONUSFARM_SQLITE_MIN_MS` | tele 샘플 최소 간격(ms), 기본 15000 |
| `CRONUSFARM_SQLITE_STATUS_MIN_MS` | status 로그 최소 간격, 기본 60000 |

## Grafana

- 시계열·화려한 그래프: **InfluxDB** (`tele` 측정, 필드 확장됨: 전 채널·`guard_*`)
- SQLite는 **이력·감사·설정 마스터** — 플러그인 `frser-sqlite-datasource` 또는 배치 조회
