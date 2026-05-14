# CronusFarm — 2004A(RepRapDiscount) EXP1/EXP2 ↔ 보드 핀 매칭

> **정본**: `arduino/CronusFarmPanel/CronusFarmPanel.ino` 상단 주석·`#else`(UNO R3)·R4 분기(직결 테스트).  
> 리본 **물리 핀 번호(1~10)** 는 제조사/기판 표식마다 다를 수 있으므로, **기능( RS / EN / D4… / BEEPER 등 )→아두이노 핀**을 기준으로 맞춘다.

---

## 운영 구성(권장): R4 메인 + R3 패널

- **R4**(`CronusFarm.ino`): WiFi·MQTT·릴레이/펌프/팬 GPIO, **I2C 마스터**.
- **R3**(`CronusFarmPanel.ino`): 2004A·엔코더·SD 등, **I2C 슬레이브 주소 `0x38`** (`panel_i2c_protocol.h`).
- **R4 ↔ R3 I2C**: R4 **SDA→A4**, **SCL→A5** ↔ R3 **A4(SDA)**, **A5(SCL)** + **GND 공통**. (로직 전압 맞출 것.)
- **USB로 R3 펌웨어 업로드 시**: R3의 **D0(RX)/D1(TX)** 에 R4 Tx/Rx를 **직결하지 말 것** — 업로더와 충돌(`programmer is not responding`). 통신은 **I2C만** 사용.

---

## 1) UNO R3 + 2004A — 핀 매칭 (현장 배선/표준 배선)

> **CronusFarm 운영( BigTreeTech 2004A + UNO R3 )** — **클릭 EXP1-2→D8**, EXP2 리본 **6번→D13**(SD CS), EXP2 **2번→D10**(MISO 등·클릭 아님). 표준 리본만(2→D13, 6→D10)이면 `docs/cronusfarm_hardware_pins.md` §3.4 의 매크로 되돌리기.

현재 저장소의 `CronusFarmPanel.ino`는 **UNO R3에서 “현장 배선(검증)” 핀맵**을 기본으로 사용한다.  
즉, 아래 두 가지 중 **어느 배선으로 물려 있는지**에 따라 코드/배선을 맞춰야 한다.

### A. 현장 배선(검증) — “R4 직결 테스트”와 동일 핀맵

> 증상 힌트: 테스트 스케치(`LiquidCrystal lcd(6,7,5,4,3,2)` + 클릭 `D8` + 엔코더 `A0/A1`)는 잘 되는데, 본 펌웨어에서 LCD가 **흰색 두 줄**이면 거의 이 케이스다.  
> 본 펌웨어는 이 핀맵을 기본으로 맞춰 둔다.

| 기능 | UNO R3 핀 |
|------|-----------|
| LCD RS / EN | D6 / D7 |
| LCD D4~D7 | D5, D4, D3, D2 |
| BTN_ENC(클릭) | D8 |
| ENC A / B | A0 / A1 |
| SD_DET / KILL | 미연결(사용 안 함) |

### B. 표준(RepRap EXP) 배선 — EXP1/EXP2 관례 핀맵

> SD/KILL까지 포함해 “정석”으로 쓰려면 이 매핑이 맞다. 이 경우에는 `CronusFarmPanel.ino`의 UNO R3 핀 정의도 **함께 되돌려야** 한다.

#### EXP1 쪽(액정·클릭·부저 — RAMPS류 관례)

| 기능(2004A/스마트 컨트롤러) | UNO R3 핀 | 비고 |
|-----------------------------|-----------|------|
| LCD **RS** | **D2** | |
| LCD **E** (Enable) | **D3** | |
| LCD **D4** | **D4** | |
| LCD **D5** | **D5** | |
| LCD **D6** | **D6** | |
| LCD **D7** | **D7** | |
| **BEEPER** | **A0** | |
| **BTN_ENC** (엔코더 클릭) | **A1** | |
| **5V / GND** | 5V / GND | 패널·리본 규격에 맞게 |

#### EXP2 쪽(SD SPI·엔코더 A/B·감지·킬)

| 기능 | UNO R3 핀 | 비고 |
|------|-----------|------|
| **ENC1** (엔코더 A) | **D8** | |
| **ENC2** (엔코더 B) | **D9** | |
| **SD CS** | **D10** | |
| **SD MOSI** | **D11** | |
| **SD MISO** | **D12** | |
| **SD SCK** | **D13** | |
| **SD 감지** (있다면) | **A2** | `PIN_SD_DET` |
| **KILL** (있다면) | **A3** | `PIN_KILL` |

`LiquidCrystal` 생성자 순서(RS, E, D4~D7)는 코드와 동일: **D2, D3, D4, D5, D6, D7**.

---

## 2) UNO R4 WiFi 메인 — `CronusFarm.ino` GPIO

릴레이/드라이버 **경유** 전제(코멘트: GPIO 직결 릴레이 코일 금지).

| 채널 / 기능 | R4 핀 |
|-------------|-------|
| LED_A1 | D2 |
| LED_A2 | D3 |
| PUMP_A1 | D4 |
| PUMP_A2 | D5 |
| LED_B1 | D6 |
| PUMP_B1 | D7 |
| PUMP_B2 | D8 |
| FAN_A1 | D9 |
| FAN_A2 | D10 |
| FAN_B1 | D11 |
| FAN_B2 | D12 |
| PUMP_C1 | A0 |
| PUMP_C2 | A1 |
| PUMP_D1 | A2 |
| PUMP_D2 | A3 |
| **I2C SDA** | **A4** |
| **I2C SCL** | **A5** |

패널 LCD 제어는 R3가 담당하고, R4는 **I2C + (Mega용) UART 패널** 경로가 있으나 UNO R3 조합에서는 **I2C가 주 경로**다.

---

## 3) 참고: R4에 2004A 직결(테스트·`CronusFarmPanel.ino` Renesas 분기)

운영 배선이 아니라 **R4 단독 + 패널** 실험 시에만 해당한다.

| 기능 | R4 핀 |
|------|-------|
| LCD RS | D6 |
| LCD EN | D7 |
| LCD D4~D7 | D5, D4, D3, D2 |
| BTN_ENC | D8 |
| BEEPER | D9 |
| ENC A / B | A0 / A1 |
| SD CS / MOSI / MISO / SCK | D10 / D11 / D12 / D13 |

---

## 4) Node-RED 대시보드와의 관계

- 대시보드 타일에 표기되는 **R4-D2 …** 등은 위 **R4 메인 핀표**와 대응한다.
- **패널(2004A) 물리 핀**은 Node-RED가 아니라 **R3 스케치**가 소유한다. UI에서 “패널 엔코더/ LCD”를 바꾸려면 **펌웨어·배선**을 바꾸고, 필요 시 대시보드 **라벨(설명 텍스트)** 만 `nodered/flows_cronusfarm_dashboard.json` 등에서 수정한다.

대시보드 JSON 수정 후 배포 절차는 **`docs/nodered_dashboard_workflow.md`** 를 본다.
