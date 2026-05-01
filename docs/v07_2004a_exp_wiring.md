# CronusFarm V0.7 — 2004A 패널 EXP1/EXP2 배선 기록

> **메모(혼동 방지)**  
> - 동일 프로젝트에서 한 번 확정된 검증 배선: RepRap 스타일 **EXP1 핀 1=GND, 2=5V** 기준으로 **EXP1-3~8 → R3 D2~D7(LCD)**, **EXP1-9~10 → R3 D8~D9(부저/클릭)**, **EXP2 → R3 D10~D11·GND·5V(엔코더)** 조합으로 동작 확인됨.  
> - 아래 표는 사용자가 정리한 **기록용 매핑**이며, 커넥터 실물 기준 **Pin 번호 체계**(Stripe/삼각 표식)가 보드마다 다를 수 있으므로 코드의 `#define`과 반드시 일치시킬 것.

---

## 1. EXP1 커넥터 (LCD 및 기본 제어)

LCD 화면 출력과 클릭 버튼, 알람 부저를 담당합니다.

| LCD (EXP1) | 아두이노 R4 핀 | 기능 | 비고 |
|------------|----------------|------|------|
| Pin 1 | D8 | 부저 (Beeper) | (8-9 스왑 반영) |
| Pin 2 | D9 | 버튼 (BTN_ENC) | (8-9 스왑 반영) |
| Pin 3 | D6 | LCD RS | (6-7 스왑 반영) |
| Pin 4 | D7 | LCD Enable | (6-7 스왑 반영) |
| Pin 5 | D5 | LCD Data 4 | |
| Pin 6 | D4 | LCD Data 5 | |
| Pin 7 | D3 | LCD Data 6 | |
| Pin 8 | D2 | LCD Data 7 | |
| Pin 9 | GND | 그라운드 | RW 핀도 여기에 접지 |
| Pin 10 | 5V | 전원 (VCC) | |

---

## 2. EXP2 커넥터 (인코더 및 SD 카드)

메뉴 이동(회전)과 데이터 저장을 담당합니다.

| LCD (EXP2) | 아두이노 R4 핀 | 기능 | 비고 |
|------------|----------------|------|------|
| Pin 1 | D12 | SD MISO | 하드웨어 SPI 고정 |
| Pin 2 | D13 | SD SCK | 하드웨어 SPI 고정 |
| Pin 3 | A0 | 인코더 회전 1 | SPI 간섭 방지 |
| Pin 4 | D10 | SD Chip Select | D10부터 사용 시작 |
| Pin 5 | A1 | 인코더 회전 2 | SPI 간섭 방지 |
| Pin 6 | D11 | SD MOSI | 하드웨어 SPI 고정 |
| Pin 7 | NC | 연결 안 함 | 비어있는 핀 |
| Pin 8 | NC | 연결 안 함 | SD 감지 (필요 시 A2) |
| Pin 9 | GND | 그라운드 | 공통 접지 |
| Pin 10 | NC | 연결 안 함 | 비상 정지 (Kill) |

---

## LiquidCrystal (R3에서 LCD만 확인했을 때의 예 — RS,E,D4~D7 순)

검증 시 사용한 **RS, E, D4, D5, D6, D7** 핀에 맞춰 아래 형태로 지정:

```cpp
// RS, E, D4, D5, D6, D7
LiquidCrystal lcd(6, 7, 5, 4, 3, 2);
```

(위 숫자는 **이 문서의 EXP1 “LCD Data/RS/EN”에 대응하는 D핀**이 `D6,D7,D5,D4,D3,D2`일 때의 예이다. 실제 `.ino`의 `#define`과 동일하게 맞출 것.)
