# CronusFarm MQTT 연결 안정화

R4 ↔ Pi Mosquitto 연결이 자주 끊길 때 점검 순서와 설정 요약.

---

## 1. 증상 구분

| 보이는 것 | 실제 의미 |
|-----------|-----------|
| 대시보드 **R4 MQTT offline** | `status` retain `offline` 또는 tele 15초 이상 없음 |
| DB `mqtt_status_log`에 **offline만 반복** | LWT·재연결 — **진짜 MQTT 끊김** |
| tele이 **1초가 아니라 ~15초** 간격 | Node-RED `CRONUSFARM_SQLITE_MIN_MS` 기본 **15000** (정상 설계) |
| UI는 자동인데 cmd 안 먹음 | 끊김 구간에 `auto_*`·`SCHED_JSON` 유실 |

Pi에서 빠른 확인:

```bash
bash ~/CronusFarm/scripts/_pi_mqtt_diag.sh
# 또는
timeout 30 mosquitto_sub -h 127.0.0.1 -t 'cronusfarm/cronusfarm-01/tele' -v
sqlite3 ~/.node-red/cronusfarm.sqlite \
  "SELECT datetime(ts_ms/1000,'localtime'), payload FROM mqtt_status_log \
   WHERE device_id='cronusfarm-01' ORDER BY ts_ms DESC LIMIT 20;"
```

---

## 2. 가장 흔한 원인 (우선순위)

### ① R4 `secrets.h` 브로커 주소

- **R4는 `*.local`·Tailscale 호스트명 해석이 안 되는 경우가 많음.**
- **`MQTT_HOST` = Pi LAN 고정 IP** (예: `192.168.60.222`), 포트 `1883`.
- PC·Node-RED는 `ida.mango-larch.ts.net` 써도 되지만, **R4는 같은 농장 LAN IP**를 써야 함.
- `tele`의 `W:` 줄: `ip=192.168.60.x` → Pi `192.168.60.222` 와 **같은 서브넷**인지 확인.

### ② WiFi 불안정 + 긴 블로킹 재연결

펌웨어 `connectWiFi()` 는 끊기면 **최대 12~20초×여러 AP + 스캔** 동안 `delay()` 로 루프가 멈춤 → MQTT keepalive 미전송 → 브로커가 세션 종료 → **retain `offline`**.

- AP를 R4 가까이, **2.4GHz 전용 SSID** 권장 (`Farm_2.4G` 등).
- 라우터: R4 MAC **DHCP 고정**, AP 격리(Isolation) 끄기.
- Pi에서 `cronusfarm/pi/wifi_ssid` 로 SSID 자주 바꾸지 않기(수신 시 `mqtt.stop()`).

### ③ tele 1Hz + 큰 페이로드

- 기본 **1초마다 ~500~600B** publish → WiFi·브로커 부하.
- 끊김이 잦으면 펌웨어 `TELEMETRY_INTERVAL_MS` 를 **2000~3000** 으로 늘리는 것을 검토.

### ④ Node-RED(Pi) MQTT 브로커 설정

- Pi에서 Node-RED는 브로커 **`127.0.0.1:1883`** 권장 (Tailscale 루프백 불필요).
- `merged-deploy.json` 의 `ida.mango-larch.ts.net` 은 **PC 원격 편집용**; Pi 배포 후 Admin에서 **127.0.0.1** 로 맞출 것.

### ⑤ UI 타임아웃이 짧음

- 대시보드: tele **15초** 없으면 offline (`TELE_MS=15000`).
- SQLite 적재도 기본 **15초** 1회 → tele 간격과 맞물려 **깜빡임** 가능.
- 완화: `CRONUSFARM_SQLITE_MIN_MS=5000` 또는 대시보드 fn에서 `TELE_MS=30000`.

---

## 3. 권장 조치 (체크리스트)

### R4 / `secrets.h`

```c
#define MQTT_HOST "192.168.60.222"   // Pi LAN — Tailscale 이름 금지
#define MQTT_PORT 1883
#define DEVICE_ID "cronusfarm-01"    // 중복 client id 없게 1대만
```

수정 후 `upcode` 로 재업로드.

### Pi Mosquitto

```bash
sudo bash ~/CronusFarm/scripts/pi-mosquitto-apply-cronusfarm-conf.sh
sudo systemctl status mosquitto
```

`deploy/mosquitto/conf.d/cronusfarm.conf` — `listener 1883 0.0.0.0`, LAN에서 R4 접근 가능해야 함.

### Node-RED 환경 (Pi)

`/etc/cronusfarm/nodered-telegram.env` 또는 Node-RED `settings.js` / systemd drop-in 예:

```bash
CRONUSFARM_SQLITE_BRIDGE_URL=http://127.0.0.1:18766
CRONUSFARM_SQLITE_MIN_MS=5000
```

브로커 노드: **Host `127.0.0.1`**, Port `1883`, Keepalive `60`.

### 펌웨어 (저장소 최신)

- `connectMqtt()` **keepalive 120초**, TCP **약 2초**, 루프당 브로커 1곳만 시도(엔코더 I2C 폴링 막힘 완화).
- **재연결** 시 `mqtt.stop()` 후 clientId를 `cronusfarm-01-r1` … 처럼 바꿔 붙임 — Mosquitto에 남은 동일 ID 세션과 겹치지 않아 CONNACK가 빨라지는 경우가 있음. **토픽**(`cronusfarm/cronusfarm-01/tele` 등)은 `DEVICE_ID` 그대로.
- 최신 `CronusFarm.ino` 반영 후 upcode.

### 감시

```bash
sudo systemctl enable --now cronusfarm-mqtt-watch.service
# 또는: bash ~/CronusFarm/scripts/pi-install-mqtt-watch.sh
```

tele 45초·브로커 TCP 실패 시 Telegram 알림 (`CRONUSFARM_MQTT_TELE_STALE_SEC`).

**자동 WiFi 복구 (2026-05):** `status` retain **offline** 이 **3분** 이상이면 `cronusfarm-mqtt-watch` 가 R4 USB로 `wifi_set`(secrets.h 1순위 AP) 실행. 재시도 간격 **30분**.

| env | 기본 | 설명 |
|-----|------|------|
| `CRONUSFARM_MQTT_AUTO_RECOVER` | 1 | 자동 복구 on/off |
| `CRONUSFARM_MQTT_AUTO_RECOVER_AFTER_SEC` | 180 | offline 지속 후 실행 |
| `CRONUSFARM_MQTT_AUTO_RECOVER_COOLDOWN_SEC` | 1800 | 복구 재시도 간격 |
| `CRONUSFARM_R4_SERIAL` | (자동) | `/dev/ttyACM*`·by-id 탐지 |

수동: `python3 ~/CronusFarm/scripts/cronusfarm_mqtt_wifi_recover.py --port /dev/ttyACM2`

---

## 4. 현장 로그 해석 (ida 기준 예)

- `mqtt_status_log`: **5분 전후로 `offline`만** → 주기적 WiFi/MQTT 재연결.
- `tele_sample`: **15초 간격** → MQTT 1Hz여도 SQLite는 15초 샘플(정상).
- `mosquitto_sub` 로 tele가 **1초마다** 오면 브로커·R4 publish 는 살아 있음 → UI offline 은 **status retain** 또는 **15s 타임아웃** 문제일 수 있음.

---

## 5. 그래도 끊기면

1. Serial 115200: `WiFi 연결 실패` / `MQTT 연결 시도` / `실패:` 코드 반복 여부.
2. 라우터에서 R4 RSSI·재연결 로그.
3. Mosquitto: `sudo journalctl -u mosquitto -f` — `Socket error` / `Client … disconnected`.
4. **client id 충돌**: 동일 `cronusfarm-01` 로 두 클라이언트가 붙으면 서로 밀어냄.

---

## 6. 관련 파일

| 항목 | 경로 |
|------|------|
| R4 MQTT 연결 | `arduino/CronusFarm/CronusFarm.ino` (`connectMqtt`, `TELEMETRY_INTERVAL_MS`) |
| secrets 예시 | `arduino/CronusFarm/secrets.h.example` |
| Mosquitto | `deploy/mosquitto/conf.d/cronusfarm.conf` |
| tele→SQLite 스로틀 | `nodered/merged-deploy.json` → `sq_fn_tele_sqlite` |
| 연결 판정 | `fn` `arduinoLastTeleMs`, `TELE_MS=15000` |
| MQTT 감시 | `scripts/cronusfarm_mqtt_watch.py`, `deploy/systemd/cronusfarm-mqtt-watch.service` |
| Pi 진단 | `scripts/_pi_mqtt_diag.sh` |
| 전 채널 ON (개발) | `scripts/pi-mqtt-force-all-on.sh`, `GET /api/device/force_all_on` |
| 텔레그램 쿨다운 적용 | `scripts/pi-apply-mqtt-telegram-cooldown.sh` |

---

## 7. MQTT 개선 로드맵 (우선순위)

| 단계 | 내용 | 상태 |
|------|------|------|
| P0 | R4 `MQTT_HOST` = Pi **LAN IP**, 2.4GHz SSID 고정, AP 격리 OFF | 현장 |
| P0 | 텔레그램 **3중 알림** 쿨다운 30분 (`pi-apply-mqtt-telegram-cooldown.sh`) | 스크립트 준비 |
| P1 | 대시보드 `TELE_MS` 15000→**30000** (깜빡임·오탐 감소) | NR fn 패치 |
| P1 | NR 오프라인 알림 **90초 지속 후 1통** (전이마다 X) | 패치 예정 |
| P1 | `TELEMETRY_INTERVAL_MS` 1000→**2000** (WiFi 부하 완화) | 펌웨어 |
| P2 | Node-RED MQTT 브로커 **127.0.0.1** 고정 (Pi) | Admin 확인 |
| P2 | `cronusfarm-mqtt-watch`만 사용, retain offline NR 알림 OFF | env |

**텔레그램이 잦은 이유**: Node-RED `status offline` + `connLineOk` + `mqtt-watch`가 각각 동작. R4 재부팅·WiFi 재연결마다 retain `offline` → 5분마다 또 알림 가능.

```bash
# Pi에서 env 일괄 적용 (SQLite 5초 샘플 + 텔레 쿨다운 30분)
bash ~/CronusFarm/scripts/pi-apply-nodered-cronusfarm-env.sh
# (별칭) bash ~/CronusFarm/scripts/pi-apply-mqtt-telegram-cooldown.sh
```

---

## 8. 차선책 (MQTT 병행·대체)

MQTT를 버리지 않고 **백업 경로**를 두는 구성이 현실적입니다.

### 8.1 HTTP tele 백업 (**구현됨**, 2026-05)

| 항목 | 설명 |
|------|------|
| API | `POST /farm/cronusfarm-sqlite/ingest/tele` JSON `{device_id, topic, raw}` |
| R4 | `publishTelemetry()`: MQTT 성공 시 MQTT만, **실패 시 HTTP** (`secrets.h` `BRIDGE_HTTP_*`) |
| Pi 브리지 | ingest 후 **MQTT tele 토픽 재발행** (`CRONUSFARM_INGEST_REPUBLISH_MQTT=1` 기본) → Node-RED·모니터 동일 |
| cmd | 아직 MQTT 전용 (2단계 예정) |

```bash
# Pi secrets.h 에 HTTP 상수 추가 (MQTT_HOST 와 동일 IP)
bash ~/CronusFarm/scripts/pi-ensure-secrets-http-backup.sh
# 펌웨어 업로드
bash ~/CronusFarm/scripts/pi-upload-r4.sh
```

Serial에 `tele→HTTP ingest` 가 보이면 MQTT 대신 HTTP 경로로 전송 중입니다.

### 8.2 USB 시리얼 백업

| 항목 | 설명 |
|------|------|
| 배선 | R4 USB → Pi (이미 프로비저닝용 연결 가능) |
| 프로토콜 | 한 줄 JSON 또는 `tele\|…` 프레임 + Pi `serial-tele-daemon` |
| 장점 | WiFi/MQTT 둘 다 죽어도 유선 |
| 단점 | 데몬·케이블 운영 부담 |

### 8.3 알림만 분리

MQTT가 살아 있어도 tele이 끊기면 알림 → **mqtt-watch**의 `TELE_STALE_SEC=60` + 쿨다운 30분으로 단일화.

### 8.4 하지 않는 것

- R3 I2C로 R4 tele 대체 — 패널 UI 전용, 릴레이 상태 아님.
- Tailscale 호스트를 R4 `MQTT_HOST`로 — mDNS/해석 실패 빈번.

---

## 9. 개발용 일괄 제어

```bash
# 전 채널 수동 ON (16ch, ui_*=1, 홀드 60분)
bash ~/CronusFarm/scripts/pi-mqtt-force-all-on.sh

# 전 채널 AUTO + 스케줄 복귀
bash ~/CronusFarm/scripts/pi-mqtt-force-all-auto.sh
```
