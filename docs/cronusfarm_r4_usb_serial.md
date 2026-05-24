# R4 USB 시리얼 primary (MQTT farm 채널 대체)

## 요약

| 항목 | MQTT (기존) | USB serial primary (신규) |
|------|-------------|---------------------------|
| tele | `cronusfarm/…/tele` | R4 `Serial.println(tele)` → Pi 데몬 → `POST /ingest/tele` |
| cmd | `mosquitto_pub …/cmd` | 브리지 → `POST :18767/r4/cmd` → 시리얼 `CMD …` |
| status | MQTT retain | `CF_STATUS online` 시리얼 |
| 업로드 | 브로커·데몬 경합 | `r4-upload.lock` + 데몬 stop/start |

**Mosquitto 전체 제거는 아님** — KMA·Node-RED 내부·기타 센서는 유지. **R4↔Pi farm tele/cmd만** USB로 분리해 WiFi/MQTT 끊김·retain 오탐을 줄입니다.

## 아키텍처

```mermaid
flowchart LR
  R4[R4 CronusFarm.ino]
  USB[/dev/ttyACM*]
  DAEMON[cronusfarm_r4_serial_daemon]
  BRIDGE[cronusfarm_sqlite_bridge :18766]
  NR[Node-RED / farm-ui]

  R4 -->|tele 줄| USB --> DAEMON -->|ingest/tele| BRIDGE
  BRIDGE -->|serial cmd API| DAEMON -->|CMD rtc_local=…| USB --> R4
  BRIDGE --> NR
```

## Pi 설치

```bash
cd ~/CronusFarm
git pull
bash scripts/pi-install-r4-serial-primary.sh
# secrets.h: CRONUSFARM_MQTT_ENABLE 0 (secrets.h.example 참고)
bash scripts/pi-upload-r4.sh
# 업로드 후 90~120초 대기(DTR 리셋·WiFi) — 시리얼 프로비저닝 직후 tele 확인 금지
bash scripts/pi-recover-r4-usb.sh
```

검증:

```bash
curl -s http://127.0.0.1:18767/health
curl -s "http://127.0.0.1:18766/api/time/status?device_id=cronusfarm-01"
```

## 복구 시나리오

### A. tele 끊김 (USB 데몬)

1. `sudo systemctl status cronusfarm-r4-serial`
2. 포트: `/etc/cronusfarm/r4-serial.env` 의 `CRONUSFARM_R4_SERIAL` (ACM 번호 변경 시 수정)
3. `bash scripts/pi-recover-r4-usb.sh`
4. 실패 시 `journalctl -u cronusfarm-r4-serial -n 80`

### B. MQTT 방식으로 롤백

```bash
bash scripts/pi-enable-r4-mqtt-fallback.sh
# secrets.h CRONUSFARM_MQTT_ENABLE 1
bash scripts/pi-upload-r4.sh
bash scripts/pi-recover-r4-mqtt-rtc.sh
```

Git 태그: `backup/pre-usb-serial-20260525` (전환 전 스냅샷)

### C. 펌웨어 업로드 후 tele 없음

- 업로드 직후 **120초** 대기 (DTR 리셋·WiFi 블록)
- `CRONUSFARM_SKIP_R4_RESET=1 bash scripts/pi-recover-r4-usb.sh`
- WiFi: `bash scripts/pi-wifi-recover-safe.sh` (mqtt-watch 중지 후)

### D. 브리지·UI는 되는데 R4 cmd만 실패

- `CRONUSFARM_R4_CMD_TRANSPORT=serial` drop-in 확인
- `curl -X POST http://127.0.0.1:18767/r4/cmd -H 'Content-Type: application/json' -d '{"payload":"rtc_local=20260525120000"}'`

## 업로드와 데몬 간섭

`pi-upload-r4.sh` 가:

1. `cronusfarm-r4-serial.service` 중지
2. `/run/cronusfarm/r4-upload.lock` 생성
3. bossac 업로드
4. trap 으로 lock 제거·데몬 재시작

## 하이브리드 권장

- **Primary**: USB tele/cmd (본 문서)
- **Backup**: `CRONUS_HTTP_TELE_BACKUP` + WiFi 시 HTTP ingest (MQTT 비활성 시에도 가능)
- **롤백**: MQTT + `pi-enable-r4-mqtt-fallback.sh`

전체 Mosquitto 제거는 Node-RED·KMA·다른 장비에 영향 — **R4 링크만 USB** 가 안정·복구 용이합니다.
