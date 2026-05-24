# CronusFarm 시각 정책 (KST)

## 두 가지 접근 비교

| | **A. Pi 시계 단일 기준** (권장) | **B. 코드마다 KST 변환** (현재 일부) |
|---|-------------------------------|-------------------------------------|
| **구성** | Pi `timedatectl` → `Asia/Seoul` + NTP. 서버·DB는 epoch ms. UI는 Pi `pi_ts_ms`를 15~60초마다 동기해 `Date.now()+skew` | 브라우저마다 `Intl`/`+9h`, NR function마다 `timeZone`/`getTime()+9h` |
| **장점** | 규칙 한 줄, PC 타임존 무관, 24h 그래프·스케줄·RTC가 같은 「지금」 | Pi TZ가 틀려도 일부 화면만 맞출 수 있음 |
| **단점** | Pi NTP·타임존 설정 필요(초기 1회) | 중복·버그(이중 +9h, 구 가드), 유지보수 비용 |
| **부팅 시** | **인터넷에서 KST를 “가져오는” 것이 아님** — NTP로 UTC 동기 + OS 타임존을 서울로 표시 | 해당 없음 |

**결론:** 부팅 시 **한 번** `Asia/Seoul`(및 NTP)만 맞추고, 이후 **운영 시각 = Pi 시계**로 통일하는 **A**가 단순하고 장점이 큽니다.  
브라우저·해외 PC에서는 **Pi `pi_ts_ms` skew**만 주기 갱신하면 됩니다.

## 계층별 역할

```text
[Pi OS] Asia/Seoul + NTP          ← scripts/pi-set-timezone-seoul.sh
    ↓
[Python bridge] cf_time.py        ← ts_ms, day_anchor_ms, pi_local_display
[Node-RED] env/로컬 시각          ← MQTT·알림(가능하면 Pi 로컬)
[Arduino RTC]                     ← Pi → rtc_local MQTT
[브라우저 farm-ui] usePiClock     ← /api/time/now skew
[NR /ui 툴바]                     ← 동일 API skew (index.html)
```

## API

| 경로 | 용도 |
|------|------|
| `GET /api/time/now` | 시계·24h 창 동기(가벼움) |
| `GET /api/time/status?device_id=` | Pi·tele·Arduino RTC 비교 |

## 예외 (명시적 KST 유지)

- **기상청(KMA)** API: 발표 시각이 KST 기준이므로 NR 수집 노드에서 KST 계산 유지.
- **epoch ms → 라벨** (DB에 저장된 과거 시각): `timeZone: Asia/Seoul` 또는 서버 `format_local(ms)` — **「지금」**과 혼동하지 말 것.

## Pi 초기 설정

```bash
sudo bash ~/CronusFarm/scripts/pi-set-timezone-seoul.sh
timedatectl status   # Time zone: Asia/Seoul
```

## 개발 시 주의

- Windows에서 로컬 테스트할 때: Python은 `cf_time`의 `ZoneInfo`, farm-ui는 **반드시** `usePiClock`/`useChartClock`의 `piNowMs()` 사용. `Date.now()`만 쓰면 PC 시각이 섞입니다.
