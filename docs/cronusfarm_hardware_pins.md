# CronusFarm 필수 핀 정의 (하드웨어 표준)

펌웨어·Node-RED `/ui` 개발환경 하드웨어 섹션과 동일한 **단일 기준**입니다.  
보드는 **R4 = Arduino UNO R4 WiFi (메인)**, **R3 = Arduino UNO R3 + BigTreeTech RepRap Smart Controller 2004A (패널)** 입니다.

---

## 1. R4 ↔ R3 패널 링크 (필수)

| 신호 | R4 핀 | R3 핀 | 비고 |
|------|-------|-------|------|
| SDA | **A4** | **A4** | I2C 슬레이브 주소 `0x38` (`panel_i2c_protocol.h`) |
| SCL | **A5** | **A5** | |
| GND | GND | GND | **필수** 공통 접지 |
| 패널 UART | 사용 안 함 | — | `CronusFarm.ino`: `CF_PANEL_LINK_I2C=1`, `CF_PANEL_LINK_UART=0` |

**금지:** R3에서 A4/A5에 엔코더 스캔용 `INPUT_PULLUP` 일괄 적용 등 I2C 버스를 망가뜨리는 설정.

---

## 2. UNO R4 WiFi — `arduino/CronusFarm/CronusFarm.ino`

릴레이/트랜지스터 경유 가정. GPIO 직결 부하 금지.

| 채널/기능 | Arduino 핀 |
|-----------|------------|
| LED A1 | D2 |
| LED A2 | D3 |
| PUMP A1 | D4 |
| PUMP A2 | D5 |
| LED B1 | D6 |
| PUMP B1 | D7 |
| PUMP B2 | D8 |
| LED B2 (B 여분) | D13 |
| FAN A1 | D9 |
| FAN A2 | D10 |
| FAN B1 | D11 |
| FAN B2 | D12 |
| PUMP C1 | A0 |
| PUMP C2 | A1 |
| PUMP D1 | A2 |
| PUMP D2 | A3 |

패널은 **I2C만** 사용합니다. R4 **Serial1(D0/D1)** 는 패널용으로 쓰지 않습니다.

---

## 3. UNO R3 + BigTreeTech 2004A — `arduino/CronusFarmPanel/CronusFarmPanel.ino`

### 3.1 I2C (R4와 동일 링크)

| 신호 | R3 핀 |
|------|-------|
| SDA | A4 |
| SCL | A5 |

### 3.2 LCD 병렬 (EXP1 / 보드 고정)

| 기능 | R3 핀 |
|------|-------|
| RS | D6 |
| EN | D7 |
| D4 | D5 |
| D5 | D4 |
| D6 | D3 |
| D7 | D2 |

#### 3.2.1 EXP1 물리 핀 — BigTreeTech 2004A **현장 검증** 기준

**2×5 IDC:** 사용자 확인 기준 **오른쪽 위 = 9번(GND)**, **오른쪽 아래 = 10번(VCC/5V)**. (다른 실크면 실크 기준으로 다시 매김.)

**엔코더 회전(A/B)은 EXP2 리본**(§3.4). **클릭(BTN_ENC)은 EXP1-2 → UNO D8** 기본(`CF_ENC_CLICK_USE_PIN`). **EXP1-2와 EXP2-2를 납으로 잇지 않아도 된다** — PCB에서 같은 네트면 자동, 아니면 EXP1-2만 D8.

| EXP1 물리 | 역할(패널) | R3(UNO) |
|-----------|------------|---------|
| **1** | **부저** 한쪽 단자 — **반대 단자는 VCC**(패널 내부에서 **통상 EXP1-10**) | **D9** (`PIN_BEEPER`) |
| **2** | **엔코더 클릭** (BTN_ENC) — 펌웨어 기본 **D8** (`CF_ENC_CLICK_USE_PIN`). EXP2-2와 **같은 네트가 아니면** EXP1-2만 D8로 납면 됨 | **D8** |
| **3** | LCD EN | **D7** |
| **4** | LCD RS | **D6** |
| **5** | LCD D4 | **D5** |
| **6** | LCD D5 | **D4** |
| **7** | LCD D6 | **D3** |
| **8** | LCD D7 | **D2** |
| **9** | GND | **GND** |
| **10** | 5V (VCC) — 부저 타단·로직 전원 | **5V** |

### 3.3 부저

§3.2.1과 동일: **EXP1-1 → D9**, 부저 **반대 단자 → VCC(보통 EXP1-10)**.

### 3.4 EXP2 리본 — 물리 핀 번호(커넥터 1번부터) ↔ Arduino

**엔코더 회전(A/B)과 SD SPI 라인**이 **EXP2** 리본으로 UNO에 감. **클릭은 기본적으로 EXP1-2→D8** 이므로 EXP2-2는 **MISO 등 SPI**로 두고 D10에 `INPUT_PULLUP`만 걸어도 됨(`CronusFarmPanel.ino` setup).

| EXP2 물리 | Arduino 핀(리본 도체) | CronusFarm **기본 배선(교차)** — UNO에서 읽는 역할 |
|-----------|------------------------|--------------------------------------------------------|
| 1 | D12 | 리본 연결, `INPUT_PULLUP` |
| 2 | **D10** | **SPI/MISO 등** (클릭 아님 — 클릭은 **EXP1-2→D8**) |
| 3 | A0 | **ENC A** |
| 4 | D11 | 리본 연결, `INPUT_PULLUP` |
| 5 | A1 | **ENC B** |
| 6 | **D13** | **SD CS** `OUTPUT`+`HIGH` (`CF_SD_CS_USE_PIN`, 기본 13) — 리본 6번을 **UNO D13**에 연결한 경우 |

`arduino/CronusFarmPanel/CronusFarmPanel.ino`: 클릭은 `clickPoll`에서 **눌림 엣지**만 큐에 넣음. 바운스로 800µs 재확인에서 LOW가 풀리면 이벤트가 사라지는 경우가 있어 기본은 재확인 없음. 스위치가 **눌렀을 때 HIGH**이면 `CF_ENC_CLICK_ACTIVE_HIGH 1`. 연속 오동작 시 `CF_ENC_CLICK_DEBOUNCE_MS` 조정.

### 3.5 UART (선택, 기본 비활성)

`CronusFarmPanel.ino` 의 `CF_R3_PANEL_UART_LINK`:

- **0 (기본):** R4↔R3 패널 **UART 배선 없음** (`gUart.begin` 미호출).
- **1:** R3 **A2** = RX, **A3** = TX (`SoftwareSerial`) ↔ R4 **Serial1** (D1 TX → R3 RX, D0 RX ← R3 TX) 교차 연결.

R3의 A2/A3와 R4의 **A2/A3(펌프 D1/D2)** 는 **서로 다른 보드의 핀**이며 직결하지 않습니다.

---

## 4. 변경 시 동기화할 위치

1. `arduino/CronusFarm/CronusFarm.ino` — `LED_*`, `PUMP_*`, `FAN_*` 상수  
2. `arduino/CronusFarmPanel/CronusFarmPanel.ino` — LCD·EXP2·`CF_R3_PANEL_UART_LINK`  
3. `docs/cronusfarm_hardware_pins.md` (본 문서, §5~§5.6 LCD 전체 상태)  
4. `nodered/panel_usage_cf_tpl.html` — 패널 사용 가이드 HTML 정본(§5.5·§5.6·전 상태 스냅샷). 수정 후 `python scripts/sync_panel_usage_into_dashboard_shell.py` 로 `flows_cronusfarm_devflow_flow.json`의 `cf_tpl_dev_panel_usage`·`cf_tpl_dev_hw_panel`(핀 요약)·Dashboard 1 `/ui` 쉘(`ui_tpl_shell_panel_usage`)에 동기  
5. `nodered/flows_cronusfarm_devflow_flow.json` → `merged-deploy.json` — `ui_tab_devflow` 그룹 **하드웨어** (`cf_grp_dev_hw`) 안 위 가이드 노드 (`cf_tpl_dev_panel_usage`, order 3) 및 `필수 핀 번호` 등  
6. Node-RED 대시보드 타일의 `cf-pin` 표기(모니터 탭) — 채널별 D/A 표기  

**배포 주의:** `scripts/deploy-cronusfarm-pi.ps1` 기본 머지는 저장소에 `nodered/CronusFarm_NodeRED_flow.json`이 있으면 **내보내기만** 사용합니다. 분할 JSON만 고쳤는데 화면에 안 보이면 `python scripts/merge_nodered_deploy.py --use-split`으로 `merged-deploy.json`을 만들거나, 배포 시 **`-UseSplitFlows`** 를 쓰고, Pi에 반영 후 브라우저 강력 새로고침을 하세요.

---

## 5. 패널 LCD — 부팅·R3 단독·R4 마스터 (`CronusFarmPanel.ino` + `CronusFarm.ino`)

### 5.1 상수

| 상수 | 값 | 의미 |
|------|-----|------|
| `BOOT_MSG_MS` (R3) | 10000 ms | R3 부팅 후 **I2C 마스터가 LCD를 한 번도 안 잡은** 상태가 이 시간 이상이면 R3가 **로컬 환영**으로 전환 |
| `PANEL_LINK_SPLASH_MIN_MS` (R4) | 5000 ms | R4가 I2C로 패널을 **처음 잡은 뒤** `CronusFarm` / WiFi / MQTT / `Dial/Push Ready` 스플래시를 **최소** 이 시간 유지(같은 루프에서 대기 화면에 덮이지 않게 함) |
| `PANEL_LINK_WAIT_MIN_MS` (R4) | 5000 ms | WiFi 미연결 **대기 화면**(`Waiting link...`)을 **최소** 이 시간 유지한 뒤에만 환영(`Welcome to`/`CronusFarm`)으로 넘어갈 수 있음 |
| `PANEL_WELCOME_MS` (R4) | 5000 ms | WiFi 연결 후 **환영** 화면 유지(또는 다이얼/푸시로 즉시 브라우즈) |

I2C 슬레이브 주소: `0x38`.

---

### 5.2 R3만 전원 (R4 없음 또는 I2C 미연결) — `CronusFarmPanel.ino`

1. **부팅 직후**  
   - 1행: `CronusFarm Panel`  
   - 2행: 공백(스페이스만 채운 줄)

2. **약 10초 후** (`BOOT_MSG_MS`, 그동안 I2C로 마스터가 LCD를 소유하지 않음 — `masterOwnsLcd`가 거짓)  
   - 1행: 소스 문자열은 `Welcome to CronusFarm`(21자)이나 `lcdWriteText`는 **앞 20자만** 쓰므로 화면에는 **`Welcome to CronusFar`** 까지(끝 `m` 잘림). 일부 각도·폰트에서 **`to`가 `2`처럼** 보일 수 있음.  
   - 2행: `gDateLine` 초기값 **`----.--.-- (---)`** + 패딩(플레이스홀더, **실제 날짜 아님**)  
   - 3행: `gTimeLine` 초기값 **`--:--:--`** + 패딩(플레이스홀더, **실제 시각 아님**)  
   - 4행: 공백  

**「3줄」이 언제냐:** 위 ②는 **R3만 켠 뒤 부팅 시각 기준 약 10초가 지난 뒤 한 번** 나온다. 그 전에는 ①(타이틀만)이 유지된다.

**날짜·시간이 실제가 아닌 이유:** R3 스케치는 **`gDateLine`/`gTimeLine`을 RTC로 갱신하지 않는다.** 초기 버퍼만 나오므로 `----.--.--`, `--:--:--`가 정상이다.

**`2000.01.01`·실제 날짜가 섞여 보일 때:**  
- **`2000.01.01` 형태**는 보통 **R4 쪽 RTC가 리셋·미보정**일 때 환영 단계(§5.3 표 순서 3)에서 **R4가 I2C로 그린 줄**이다. R3 단독 플레이스홀더는 `----` 쪽이 기본이다.  
- **「Welcome to / (2행 빈칸) / 실제 날짜 / 실제 시각」** 조합은 펌웨어가 의도한 **한 화면 구성은 아니다.** 정상 R4 환영은 **2행에 반드시 `CronusFarm`**이 온다(`lcdWelcomeIfOk`). 빈 2행 + 3·4만 실시간이면 **I2C로 특정 행만 도착·나머지 잔상**이거나, **행 번호를 1부터 세는 착시** 가능성을 의심한다.

---

### 5.3 R4 마스터(I2C) — 시간 순서

**공통:** 아래 1→2→…는 R4가 부팅·리셋한 뒤 **I2C로 R3 슬레이브(`0x38`)를 처음 잡은 시점**부터 이어진다. ① 스플래시는 **그 직후 한 번** 그려지고, `PANEL_LINK_SPLASH_MIN_MS`(5초) 동안 `lcdRenderUi`가 대기 화면으로 **덮어쓰지 않는다**(안 보면 놓치기 쉬움).

| 순서 | 언제(조건) | 1행 | 2행 | 3행 | 4행 | 최소 유지 |
|------|------------|-----|-----|-----|-----|-----------|
| 1 | R4 `panelI2cPing` 성공 직후, I2C 링크 최초 | `CronusFarm` | `WiFi OK` 또는 `WiFi --` | **WiFi가 끊기면 `MQTT --` 고정**(내부 연결 잔상과 무관) | `Dial/Push Ready` | **5초** (`PANEL_LINK_SPLASH_MIN_MS`) — 다음 화면으로 넘어가기 전에 확인용 |
| 2 | 스플래시 타이머 종료 후, **아직 WiFi 미연결** | `LED A1 D2` | `WiFi --  MQTT --` 등(`%s %s`로 인해 **공백 두 칸**) | `Waiting link...` | (공백 20칸) | **5초** (`PANEL_LINK_WAIT_MIN_MS`) — 이후 WiFi가 붙으면 환영으로 |
| 3 | **WiFi 연결됨** + 스플래시·대기 타이머 조건 충족 후 `lcdWelcomeIfOk` | `Welcome to` | `CronusFarm` | RTC 날짜 또는 `RTC -- set time` | `hh:mm:ss AM/PM` 또는 `--:--:--` | **5초** (`PANEL_WELCOME_MS`, 다이얼 입력 시 즉시 브라우즈로 넘어갈 수 있음) |
| 4 | 환영 창이 끝난 뒤 **브라우즈** (`lcdBrowseDraw`) | `LED A1 (D2)` 등 | `MODE:AUTO` 또는 `MODE:MAN ` | `STATE:…    CHx/15` | `Dial:Next, Push:Edit` | — |
| 5 | **EDIT** | `Setting Mode (EDIT)` | 채널·핀 | `SET:OFF` / `SET:ON` / `SET:AUTO` | `Dial:Sel Push:OK` | — |

**날짜·시각 줄(순서 3):**  
- RTC가 정상이면 **실제 날짜·12시간제 시각**이 나온다.  
- **부팅 1회** `rtcEnsureValidOnce`: 칩이 무효·연도 범위 밖이면 **2025-12-22 09:00:00** 으로 기록(이후 NTP·수동 교정).  
- `RTC.getTime` 실패 시 3·4행은 `RTC -- set time` / `--:--:--` 고정 문자열이다.

**R4 가동 중 R3만 리셋:** R4는 I2C 응답이 **약 1.5초 이상** 없으면 패널 링크를 끊고, 재 `panelI2cPing` 시 스플래시·동기를 다시 한다. 이미 환영된 세션에서도 **스플래시 유지 시간** 동안 `lcdBrowseDraw`가 덮어쓰지 않는다. 브라우즈는 I2C 경로에서 **4행을 매 갱신마다 전송**해 빈 줄을 줄인다.

**다이얼:**  
- **브라우즈:** 회전 = 채널 **다음/이전**(UI 순서 15개), 누름 = **EDIT** 진입. 환영 5초 안 **첫** 입력은 **CH1부터** 브라우즈를 시작하도록 처리된다.  
- **EDIT:** 회전 = **OFF → ON → AUTO** 순환(`chAuto`·펌웨어 펌프 주기·Pi `auto_*`/스케줄), 누름 = 적용 후 브라우즈(긴 비프).

---

### 5.4 브라우즈에서 «2행이 비어 있다»처럼 보일 때 (현장 사진과 동일 증상 가능)

펌웨어 `lcdBrowseDraw()`는 **LCD 2행(0부터 세면 인덱스 1)** 에 항상 다음을 보냅니다.

- `MODE:AUTO` 또는 `MODE:MAN ` (끝에 공백 한 칸 포함)

즉 **소스 코드만 보면 2행이 완전 공백인 정상 경로는 없다.** 그럼에도 **1행 `LED A1 (D2)`, 3·4행은 맞고 2행만 비어 보이는** 경우 분석:

1. **I2C `SET_LINE` 한 줄이 실패했는데 R4가 성공으로 취급하던 버그(수정됨):** `Wire.endTransmission()`이 NACK 등으로 실패해도 **행 캐시만 갱신**되면, 다음 루프에서 «이미 보냈다»고 판단해 **2행을 재전송하지 않을 수 있었다.** 현재는 **전송 실패 시 캐시를 건드리지 않아** 다음 주기에 재시도한다.  
2. **버스·배선:** 긴 리본, GND 미스, 노이즈로 **특정 행 패킷만 깨짐**.  
3. **대비·시야:** `MODE:` 글자가 작고 상단이라 **빈 줄로 착시**.  
4. **행 번호 착시:** 사용자가 말하는 «2행」이 LCD **물리 3번째 줄**(인덱스 2)을 가리키는 경우, 그 줄은 원래 `STATE:…`이어야 하며 비어 있으면 2번과 동일하게 **부분 전송** 의심.

**언제 나타나나:** 순서 표 **4번 브라우즈** — `PANEL_WELCOME_MS`가 지난 뒤(또는 환영 중 다이얼로 바로 진입한 뒤) **채널 브라우즈**가 그려질 때. 1행이 `LED A1 (D2)` 형태면 **CH1(LED A1)** 기준 화면이다.

확인: 최신 `CronusFarm.ino` 업로드 후에도 동일하면 **I2C·GND·풀업**을 재점검한다.

---

### 5.5 패널 20×4 LCD 스냅샷 (부팅·리셋, 펌웨어 문자열 일치)

테두리 `|` 안은 **실제 20열**이다. R4는 `panelPrintLine()`이 왼쪽 정렬 후 공백으로 20열을 채운다. R3 환영 0행 `Welcome to CronusFarm`은 **21자**라 `lcdWriteText`가 **앞 20자만** 쓴다 → 화면에는 `Welcome to CronusFar`까지 보인다.

#### A. R3만 전원 (I2C 마스터 없음)

**① 리셋 직후** (`lcdShowBootMessage`)

```
+--------------------+
|CronusFarm Panel    |
|                    |
|                    |
|                    |
+--------------------+
```

**② 약 10초 후** (`BOOT_MSG_MS`, `lcdShowWelcomeMessage`)

```
+--------------------+
|Welcome to CronusFar|
|----.--.-- (---)    |
|--:--:--            |
|                    |
+--------------------+
```

(`gDateLine` 리터럴은 19자 + LCD가 한 칸 공백으로 20열을 채울 수 있음. 위 2행은 **20열 박스**에 맞춘 표기.)

#### B. R4 + R3 I2C (`CF_PANEL_LINK_I2C`)

**③ 스플래시** (최소 약 5초, WiFi·MQTT 연결 예)

```
+--------------------+
|CronusFarm          |
|WiFi OK             |
|MQTT OK             |
|Dial/Push Ready     |
+--------------------+
```

WiFi·MQTT 미연결 예:

```
+--------------------+
|CronusFarm          |
|WiFi --             |
|MQTT --             |
|Dial/Push Ready     |
+--------------------+
```

**④ WiFi 연결 전 대기** (최소 약 5초)

```
+--------------------+
|LED A1 D2           |
|WiFi --  MQTT --    |
|Waiting link...     |
|                    |
+--------------------+
```

(2행은 `snprintf(..., "%s %s", "WiFi --", " MQTT --")` 형태라 WiFi 끝과 `M` 사이에 **스페이스가 두 칸** 들어간 뒤 20열로 맞춘다. WiFi/MQTT 연결 조합에 따라 `WiFi OK  MQTT OK` 등 4종이 나온다 — 전체는 §5.6·`panel_usage_cf_tpl.html`.)

**⑤ WiFi OK 후 환영** (RTC 정상 가정 예시)

```
+--------------------+
|Welcome to          |
|CronusFarm          |
|2026.05.12 (Mon)    |
|12:34:56 PM         |
+--------------------+
```

**⑥ 브라우즈** (CH1 LED A1, 수동·OFF 예. 2행은 `MODE:MAN ` 끝 공백 포함 9자 + 패딩 → 화면은 아래와 같이 20열)

```
+--------------------+
|LED A1 (D2)         |
|MODE:MAN            |
|STATE:OFF    CH1/15 |
|Dial:Next, Push:Edit|
+--------------------+
```

**⑥′ 현장에서 2행만 비어 보일 때** (1·3·4행은 위와 유사) — 원인은 §5.4.

```
+--------------------+
|LED A1 (D2)         |
|                    |
|STATE:OFF    CH1/15 |
|Dial:Next, Push:Edit|
+--------------------+
```

**⑦ EDIT**

```
+--------------------+
|Setting Mode (EDIT) |
|LED A1 (D2)         |
|SET:OFF             |
|Dial:Sel Push:OK    |
+--------------------+
```

**⑦′ EDIT · SET:ON** (같은 레이아웃, 3행만 `SET:ON` + 패딩)

```
+--------------------+
|Setting Mode (EDIT) |
|LED A1 (D2)         |
|SET:ON              |
|Dial:Sel Push:OK    |
+--------------------+
```

**⑦″ EDIT · SET:AUTO**

```
+--------------------+
|Setting Mode (EDIT) |
|LED A1 (D2)         |
|SET:AUTO            |
|Dial:Sel Push:OK    |
+--------------------+
```

---

### 5.6 LCD 전체 상태 카탈로그 (캡처 스타일)

**스플래시(B):** WiFi OK/-- × MQTT OK/-- **4조합** 각각 4행 스냅샷 — 위 §5.5 ③과 같은 틀.

**대기(C):** 1행 기본 `LED A1 D2`(`gUiCh==0`). 2행 **4조합**(`WiFi --  MQTT --`, `WiFi --  MQTT OK`, `WiFi OK  MQTT --`, `WiFi OK  MQTT OK`). 3·4행 동일.

**환영(D):** RTC 정상 예시(§5.5 ⑤) / `RTC -- set time` + `--:--:--` / 미보정 **`2000.xx.xx`** 예시 — `panel_usage_cf_tpl.html`의 D-1~D-3.

**브라우즈(E):** `MODE:AUTO|MAN`, `STATE:ON|OFF`, CH1~15에 따라 1·3행만 변함. 대표 스냅샷·**이상(2행 공백)**·**15채널 1행 표**는 HTML 정본에 모두 있음.

**R3 CLEAR 직후:** 잠깐 네 줄이 비어 보일 수 있음(곧바로 `SET_LINE`으로 채움).

**`/ui` 개발환경(쉘 탭)** 및 **`/nrdb2`** 사용 가이드 UI 정본: `nodered/panel_usage_cf_tpl.html` — 수정 후 `python scripts/sync_panel_usage_into_dashboard_shell.py` 및 `merge_nodered_deploy.py --use-split`으로 반영한다.

