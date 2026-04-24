/*
  CronusFarm — UNO R3 패널 전용 (RepRapDiscount Smart Controller 2004A)

  역할: LCD / 엔코더 / 클릭 / 부저 / SD / KILL / SD 감지
  통신: I2C 슬레이브 (마스터는 UNO R4 WiFi), SDA=A4 SCL=A5

  EXP1 → (기존) UNO R3 / (변경) Trigorilla(Mega2560)
    - UNO R3:  BEEPER A0, BTN_ENC A1, LCD RS D2, LCD EN D3, LCD D4~D7 → D4~D7
    - Mega2560(Trigorilla 1.4 계열, Marlin 핀 기준):
      BEEPER D37, BTN_ENC D35, LCD RS D16, LCD EN D17, LCD D4/D5/D6/D7 = D23/D25/D27/D29
      ENC1 D31, ENC2 D33, KILL D41, SD DETECT D49, SD CS D53(SDSS)
  EXP2 → (기존) UNO R3 / (변경) Trigorilla(Mega2560)
    - UNO R3:  SD MISO D12, SCK D13, ENC1 D8, SD CS D10, ENC2 D9, MOSI D11, SD DETECT A2, KILL A3
    - Mega2560: EXP2는 SD SPI/엔코더/킬 스위치가 분산되어 있으며 위 핀을 사용
*/

#include <Wire.h>
#include <SPI.h>
#include <SD.h>
#include <string.h>
#include <LiquidCrystal.h>
#include "panel_i2c_protocol.h"

// ============================================================
// 핀 정의
// - UNO R3(기존): 주석 상단의 EXP1/EXP2 매핑
// - Trigorilla(Mega2560): Marlin pins_TRIGORILLA_14.h / Trigorilla 핀 PDF 기준(RepRapDiscount Smart Controller)
#if defined(ARDUINO_AVR_MEGA2560) || defined(ARDUINO_AVR_MEGA)
// RepRapDiscount Smart Controller + RAMPS 계열(Marlin 기준): BTN_EN1=31, BTN_EN2=33, BTN_ENC=35, BEEPER=37
// (이전에 BEEPER를 31로 두면 ENC_A(31)과 핀이 겹쳐 엔코더가 죽습니다.)
static const int PIN_BEEPER = 37;      // BEEPER_PIN
static const int PIN_ENC_CLICK = 35;   // BTN_ENC
static const int PIN_LCD_RS = 16;      // LCD_PINS_RS
static const int PIN_LCD_EN = 17;      // LCD_PINS_ENABLE
static const int PIN_LCD_D4 = 23;      // LCD_PINS_D4
static const int PIN_LCD_D5 = 25;      // LCD_PINS_D5
static const int PIN_LCD_D6 = 27;      // LCD_PINS_D6
static const int PIN_LCD_D7 = 29;      // LCD_PINS_D7
static const int PIN_ENC_A = 31;       // BTN_EN1 (주의: R3와 다름)
static const int PIN_ENC_B = 33;       // BTN_EN2
static const int PIN_SD_CS = 53;       // SDSS (Mega2560 HW SS)
static const int PIN_SD_DET = 49;      // SD_DETECT_PIN
static const int PIN_KILL = 41;        // KILL_PIN
#else
static const int PIN_BEEPER = A0;
static const int PIN_ENC_CLICK = A1;
static const int PIN_LCD_RS = 2;
static const int PIN_LCD_EN = 3;
static const int PIN_LCD_D4 = 4;
static const int PIN_LCD_D5 = 5;
static const int PIN_LCD_D6 = 6;
static const int PIN_LCD_D7 = 7;
static const int PIN_ENC_A = 8;
static const int PIN_ENC_B = 9;
static const int PIN_SD_CS = 10;
static const int PIN_SD_DET = A2;
static const int PIN_KILL = A3;
#endif

static LiquidCrystal lcd(PIN_LCD_RS, PIN_LCD_EN, PIN_LCD_D4, PIN_LCD_D5, PIN_LCD_D6, PIN_LCD_D7);

// ============================================================
// Trigorilla 확장 출력(펌프 + RGB 상태 LED)
// - 메인보드 R4가 I2C로 펌프 상태(비트마스크)를 내려보냅니다.
// - HEATER0/HEATER1/HOTBED 제어핀을 R/G/B 상태 LED로 사용해 순차 점멸합니다.
#if defined(ARDUINO_AVR_MEGA2560) || defined(ARDUINO_AVR_MEGA)
static const int PIN_PUMP_A1 = 11; // SERVO0
// SERVO1: Marlin RAMPS/Trigorilla 계열은 보통 D6. A2만 무반응이면 보드 실크/Marlin pins의 SERVO1_PIN을 확인.
static const int PIN_PUMP_A2 = 6;  // SERVO1
static const int PIN_PUMP_B1 = 5;  // SERVO2
static const int PIN_PUMP_B2 = 4;  // SERVO3

static const int PIN_LED_R = 10;   // HEATER0 제어핀
static const int PIN_LED_G = 45;   // HEATER1 제어핀
// HOTBED(D8)은 11A 입력이 없으면 스크류 단자 출력이 안 보일 수 있어,
// “연결 확인용”으로는 5A 라인에서 동작하는 FAN0(D9)로 B를 매핑합니다.
// (필요 시 다시 HOTBED(D8)로 되돌릴 수 있음)
static const int PIN_LED_B = 9;    // FAN0 제어핀(5A 라인 가시성)

static uint8_t gPumpMask = 0;
static bool gSawMasterCmd = false;

static void applyPumpMask(uint8_t mask) {
  gPumpMask = (uint8_t)(mask & 0x0F);
  gSawMasterCmd = true;
  digitalWrite(PIN_PUMP_A1, (gPumpMask & 0x01) ? HIGH : LOW);
  digitalWrite(PIN_PUMP_A2, (gPumpMask & 0x02) ? HIGH : LOW);
  digitalWrite(PIN_PUMP_B1, (gPumpMask & 0x04) ? HIGH : LOW);
  digitalWrite(PIN_PUMP_B2, (gPumpMask & 0x08) ? HIGH : LOW);
}

static void rgbBlinkTick() {
  static uint32_t last = 0;
  static uint8_t phase = 0;
  const uint32_t now = millis();
  if (now - last < 500) return;
  last = now;
  phase = (uint8_t)((phase + 1) % 3);

  digitalWrite(PIN_LED_R, (phase == 0) ? HIGH : LOW);
  digitalWrite(PIN_LED_G, (phase == 1) ? HIGH : LOW);
  digitalWrite(PIN_LED_B, (phase == 2) ? HIGH : LOW);
}
#endif

struct QueEvt {
  uint8_t t;
  uint8_t p;
};
static QueEvt gQ[8];
static uint8_t gQLen = 0;

// I2C 점검: R4(requestFrom) 호출 여부/횟수
static volatile uint32_t gI2cReqCount = 0;
static volatile uint32_t gI2cLastReqMs = 0;

static void qPush(uint8_t t, uint8_t p) {
  if (gQLen >= 8) {
    return;
  }
  gQ[gQLen].t = t;
  gQ[gQLen].p = p;
  gQLen++;
}

static void onRequestHandler() {
  // R4가 requestFrom()을 호출하면 여기로 들어옵니다. (I2C R4↔Panel 통신 여부 판별용)
  gI2cReqCount++;
  gI2cLastReqMs = millis();

  uint8_t sendN = gQLen;
  if (sendN > 7) {
    sendN = 7;
  }
  Wire.write(sendN);
  for (uint8_t i = 0; i < sendN; i++) {
    Wire.write(gQ[i].t);
    Wire.write(gQ[i].p);
  }
  uint8_t left = (uint8_t)(gQLen - sendN);
  for (uint8_t i = 0; i < left; i++) {
    gQ[i] = gQ[i + sendN];
  }
  gQLen = left;
}

static void beepShortLocal() {
  for (int i = 0; i < 80; i++) {
    digitalWrite(PIN_BEEPER, HIGH);
    delayMicroseconds(125);
    digitalWrite(PIN_BEEPER, LOW);
    delayMicroseconds(125);
  }
}

static void beepLongLocal() {
  for (int i = 0; i < 400; i++) {
    digitalWrite(PIN_BEEPER, HIGH);
    delayMicroseconds(125);
    digitalWrite(PIN_BEEPER, LOW);
    delayMicroseconds(125);
  }
}

static void lcdWriteLine20(uint8_t row, const char line20[20]) {
  lcd.setCursor(0, row);
  for (uint8_t i = 0; i < 20; i++) {
    lcd.write((uint8_t)line20[i]);
  }
}

// Wire.onReceive는 AVR에서 인터럽트 경로로 들어올 수 있어, LCD/부저/펌프 등
// 무거운 처리를 여기서 하면 엔코더 폴링·슬레이브 동작이 불안정해질 수 있습니다.
static volatile bool gI2cRxPending = false;
static uint8_t gI2cRxLen = 0;
static uint8_t gI2cRxBuf[32];
// R4(마스터)가 LCD 갱신 명령을 보냈는지(그리고 최근인지) 확인하기 위한 플래그/시각
static bool gSawLcdCmd = false;
static uint32_t gLastLcdCmdMs = 0;

static void onReceiveHandler(int /*numBytes*/) {
  uint8_t n = 0;
  while (Wire.available() && n < (uint8_t)sizeof(gI2cRxBuf)) {
    gI2cRxBuf[n++] = (uint8_t)Wire.read();
  }
  if (n == 0) {
    return;
  }
  gI2cRxLen = n;
  gI2cRxPending = true;
}

static void processI2cMasterRx() {
  if (!gI2cRxPending) {
    return;
  }

  uint8_t rx[32];
  uint8_t rlen;
  noInterrupts();
  if (!gI2cRxPending) {
    interrupts();
    return;
  }
  rlen = gI2cRxLen;
  if (rlen > sizeof(rx)) {
    rlen = (uint8_t)sizeof(rx);
  }
  memcpy(rx, gI2cRxBuf, rlen);
  gI2cRxPending = false;
  interrupts();

  uint8_t i = 0;
  while (i < rlen) {
    uint8_t op = rx[i++];
    if (op == PANEL_CMD_CLEAR) {
      gSawLcdCmd = true;
      gLastLcdCmdMs = millis();
      lcd.clear();
      continue;
    }

    if (op == PANEL_CMD_SET_LINE) {
      if ((uint8_t)(rlen - i) < 2) {
        break;
      }
      uint8_t row = rx[i++];
      uint8_t len = rx[i++];
      if (row > 3) row = 3;
      if (len > 20) len = 20;
      if ((uint8_t)(rlen - i) < len) {
        break;
      }

      char line20[20];
      for (uint8_t k = 0; k < 20; k++) {
        line20[k] = ' ';
      }
      for (uint8_t k = 0; k < len; k++) {
        line20[k] = (char)rx[i + k];
      }
      i = (uint8_t)(i + len);
      gSawLcdCmd = true;
      gLastLcdCmdMs = millis();
      lcdWriteLine20(row, line20);
      continue;
    }

    if (op == PANEL_CMD_BEEP) {
      if ((uint8_t)(rlen - i) < 1) {
        break;
      }
      uint8_t m = rx[i++];
      if (m == 0) beepShortLocal();
      else beepLongLocal();
      continue;
    }

    if (op == PANEL_CMD_SET_PUMPS) {
      if ((uint8_t)(rlen - i) < 1) {
        break;
      }
      uint8_t mask = rx[i++];
#if defined(ARDUINO_AVR_MEGA2560) || defined(ARDUINO_AVR_MEGA)
      applyPumpMask(mask);
#endif
      continue;
    }

    break;
  }
}

static int8_t gEncPrevAB = 0;
static uint32_t gEncLastMs = 0;
static int8_t gEncPrevA = -1;
static int8_t gEncPrevB = -1;
// 엔코더 민감도(누적 스텝 수). 값이 클수록 “더 많이 돌려야” 이벤트가 1번 발생합니다.
// 현재 UI는 사실상 ON/OFF(2개 선택) 위주라, 과민하면 오조작이 쉬워 1/4회전 체감이 되도록 완화합니다.
static const int8_t ENC_STEPS_PER_EVENT = 7;
static int8_t gEncAccum = 0;

static void encoderPoll() {
  uint32_t now = millis();
  if (now - gEncLastMs < 2) {
    return;
  }
  gEncLastMs = now;

  int a = digitalRead(PIN_ENC_A) ? 1 : 0;
  int b = digitalRead(PIN_ENC_B) ? 1 : 0;
  int8_t ab = (int8_t)((a << 1) | b);

  static const int8_t delta[16] = {
    0, +1, -1, 0,
    -1, 0, 0, +1,
    +1, 0, 0, -1,
    0, -1, +1, 0
  };
  int8_t idx = (int8_t)((gEncPrevAB << 2) | ab);
  int8_t d = delta[(uint8_t)idx];
  gEncPrevAB = ab;

  // 일부 패널/케이블에서 EN1/EN2가 반대로 연결되거나 신호가 약하면 위 테이블이 0만 나오는 경우가 있어
  // A/B 변화 자체를 기준으로 “보수적으로” 한 스텝을 만들어냅니다(방향은 최선 추정).
  if (gEncPrevA < 0 || gEncPrevB < 0) {
    gEncPrevA = (int8_t)a;
    gEncPrevB = (int8_t)b;
    return;
  }

  if (d == 0 && (a != gEncPrevA || b != gEncPrevB)) {
    // 변화가 있었다면 방향을 추정: A가 바뀌었을 때의 B 상태로 결정(일반적인 2상 엔코더 규칙 기반)
    if (a != gEncPrevA) {
      d = (b == a) ? +1 : -1;
    } else {
      d = (a != b) ? +1 : -1;
    }
  }
  gEncPrevA = (int8_t)a;
  gEncPrevB = (int8_t)b;

  if (d == 0) {
    return;
  }

  // 스텝 누적 후, 임계치에 도달했을 때만 이벤트 발생
  gEncAccum = (int8_t)(gEncAccum + d);
  if (gEncAccum >= ENC_STEPS_PER_EVENT) {
    gEncAccum = 0;
    qPush(PANEL_EVT_ENC_CW, 0);
  } else if (gEncAccum <= (int8_t)(-ENC_STEPS_PER_EVENT)) {
    gEncAccum = 0;
    qPush(PANEL_EVT_ENC_CCW, 0);
  }
}

static uint32_t gBtnLastMs = 0;
static bool gBtnPrev = true;

static void clickPoll() {
  bool cur = digitalRead(PIN_ENC_CLICK) ? true : false;
  bool pressed = (gBtnPrev == true && cur == false);
  gBtnPrev = cur;
  if (!pressed) {
    return;
  }
  uint32_t now = millis();
  if (now - gBtnLastMs < 220) {
    return;
  }
  gBtnLastMs = now;
  qPush(PANEL_EVT_CLICK, 1);
}

static bool gKillPrev = false;

static void killPoll() {
  bool pressed = (digitalRead(PIN_KILL) == LOW);
  if (pressed && !gKillPrev) {
    qPush(PANEL_EVT_KILL, 1);
  }
  gKillPrev = pressed;
}

static bool gSdPrev = false;
static bool gSdInited = false;

static void sdDetectPoll() {
  bool present = (digitalRead(PIN_SD_DET) == LOW);
  if (!gSdInited) {
    gSdPrev = present;
    gSdInited = true;
    qPush(PANEL_EVT_SD, present ? 1u : 0u);
    return;
  }
  if (present != gSdPrev) {
    gSdPrev = present;
    qPush(PANEL_EVT_SD, present ? 1u : 0u);
  }
}

void setup() {
#if defined(ARDUINO_AVR_MEGA2560) || defined(ARDUINO_AVR_MEGA)
  pinMode(PIN_PUMP_A1, OUTPUT);
  pinMode(PIN_PUMP_A2, OUTPUT);
  pinMode(PIN_PUMP_B1, OUTPUT);
  pinMode(PIN_PUMP_B2, OUTPUT);
  applyPumpMask(0);

  pinMode(PIN_LED_R, OUTPUT);
  pinMode(PIN_LED_G, OUTPUT);
  pinMode(PIN_LED_B, OUTPUT);
  digitalWrite(PIN_LED_R, LOW);
  digitalWrite(PIN_LED_G, LOW);
  digitalWrite(PIN_LED_B, LOW);
#endif

  pinMode(PIN_BEEPER, OUTPUT);
  digitalWrite(PIN_BEEPER, LOW);

  pinMode(PIN_ENC_CLICK, INPUT_PULLUP);
  pinMode(PIN_ENC_A, INPUT_PULLUP);
  pinMode(PIN_ENC_B, INPUT_PULLUP);
  pinMode(PIN_SD_DET, INPUT_PULLUP);
  pinMode(PIN_KILL, INPUT_PULLUP);

  lcd.begin(20, 4);
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("CronusFarm Panel");
  lcd.setCursor(0, 1);
  lcd.print("I2C slave ready");

  SPI.begin();
  if (SD.begin(PIN_SD_CS)) {
    lcd.setCursor(0, 2);
    lcd.print("SD: OK           ");
  } else {
    lcd.setCursor(0, 2);
    lcd.print("SD: (no/fail)    ");
  }

  Wire.begin(PANEL_I2C_ADDR);
  Wire.onReceive(onReceiveHandler);
  Wire.onRequest(onRequestHandler);
}

void loop() {
  processI2cMasterRx();
  encoderPoll();
  clickPoll();
  killPoll();
  sdDetectPoll();
#if defined(ARDUINO_AVR_MEGA2560) || defined(ARDUINO_AVR_MEGA)
  rgbBlinkTick();
  // 주의: R4가 LCD를 제어하는 동안에는(최근 SET_LINE/CLEAR를 받은 동안) 아래 디버그 출력이 화면을 덮어쓰지 않게 합니다.
  // R4 LCD 갱신이 안 올 때만 “I2C 연결/펌프 마스크”를 확인할 수 있도록 하단 1줄만 표시합니다.
  static uint32_t lastUi = 0;
  const uint32_t now = millis();
  const bool masterOwnsLcd = gSawLcdCmd && (now - gLastLcdCmdMs) < 2000;
  if (now - lastUi >= 500) {
    lastUi = now;
    if (!masterOwnsLcd) {
      lcd.setCursor(0, 3);
      // R4의 요청/명령 수신 여부를 함께 표시
      const uint32_t reqCnt = gI2cReqCount;
      const uint32_t ageMs = (gI2cLastReqMs == 0) ? 0xFFFFFFFFu : (now - gI2cLastReqMs);
      if (!gSawMasterCmd) {
        // 아직 SET_PUMPS를 못 받았을 때: requestFrom이 오는지부터 확인
        char b[21];
        if (ageMs == 0xFFFFFFFFu) {
          snprintf(b, sizeof(b), "I2C REQ:0 (none) ");
        } else {
          snprintf(b, sizeof(b), "I2C REQ:%lu %4lums",
                   (unsigned long)reqCnt,
                   (unsigned long)ageMs);
        }
        lcd.print(b);
      } else {
        char b[21];
        snprintf(b, sizeof(b), "PUMPS:%c%c%c%c R%lu",
                 (gPumpMask & 0x01) ? '1' : '0',
                 (gPumpMask & 0x02) ? '1' : '0',
                 (gPumpMask & 0x04) ? '1' : '0',
                 (gPumpMask & 0x08) ? '1' : '0',
                 (unsigned long)reqCnt);
        lcd.print(b);
      }
    }
  }
#endif
}
