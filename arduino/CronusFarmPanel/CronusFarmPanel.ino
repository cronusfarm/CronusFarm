/*
  CronusFarm — UNO R3 패널 전용 (RepRapDiscount Smart Controller 2004A)

  역할: LCD / 엔코더 / 클릭 / 부저 / SD / KILL / SD 감지
  통신: UART(Serial1, Mega D19/D18) + USB Serial(시간 동기)

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
// Pi 시간 동기(USB Serial)
// - Pi가 주기적으로 아래 라인을 전송하면 LCD 환영화면의 날짜/시간을 갱신합니다.
//   DT:2026.04.24 (Fri)
//   TM:13:45:12
static char gDateLine[21] = "----.--.-- (---)   ";
static char gTimeLine[21] = "--:--:--            ";
static bool gWelcomeShown = false;
static uint32_t gBootAtMs = 0;
static const uint32_t BOOT_MSG_MS = 10000;
static uint32_t gLastLcdInitMs = 0;

// ============================================================
// Trigorilla 확장 출력(펌프 + RGB 상태 LED)
// - 메인보드 R4가 I2C로 펌프 상태(비트마스크)를 내려보냅니다.
// - HEATER0/HEATER1/HOTBED 제어핀을 R/G/B 상태 LED로 사용해 순차 점멸합니다.
#if defined(ARDUINO_AVR_MEGA2560) || defined(ARDUINO_AVR_MEGA)
// 원격 제어 채널(요청 매핑)
// - FAN: I2C(X-/X+/Y-/Y+) 실크 라벨에 해당하는 GPIO를 사용
// - SERVO0~3: SERVO 헤더의 제어 GPIO(일반적으로 PWM 가능)
static const int PIN_FAN_A1 = 3;   // I2C X-
static const int PIN_FAN_A2 = 2;   // I2C X+
static const int PIN_FAN_B1 = 14;  // I2C Y-
static const int PIN_FAN_B2 = 15;  // I2C Y+

static const int PIN_SERVO0 = 11;  // SERVO0
static const int PIN_SERVO1 = 6;   // SERVO1
static const int PIN_SERVO2 = 5;   // SERVO2
static const int PIN_SERVO3 = 4;   // SERVO3

static const int PIN_LED_R = 10;   // HEATER0 제어핀
static const int PIN_LED_G = 45;   // HEATER1 제어핀
// HOTBED(D8)은 11A 입력이 없으면 스크류 단자 출력이 안 보일 수 있어,
// “연결 확인용”으로는 5A 라인에서 동작하는 FAN0(D9)로 B를 매핑합니다.
// (필요 시 다시 HOTBED(D8)로 되돌릴 수 있음)
static const int PIN_LED_B = 9;    // FAN0 제어핀(5A 라인 가시성)

static bool gSawMasterCmd = false;
// 원격 출력 상태(8개: FAN 4개 + SERVO 4개)
static bool gRemoteOut[8] = { false, false, false, false, false, false, false, false };

static void applyRemoteOut(uint8_t idx, bool on) {
  if (idx > 7) return;
  gRemoteOut[idx] = on;
  gSawMasterCmd = true;
  switch (idx) {
    case 0: digitalWrite(PIN_FAN_A1, on ? HIGH : LOW); break;
    case 1: digitalWrite(PIN_FAN_A2, on ? HIGH : LOW); break;
    case 2: digitalWrite(PIN_FAN_B1, on ? HIGH : LOW); break;
    case 3: digitalWrite(PIN_FAN_B2, on ? HIGH : LOW); break;
    case 4: digitalWrite(PIN_SERVO0, on ? HIGH : LOW); break;
    case 5: digitalWrite(PIN_SERVO1, on ? HIGH : LOW); break;
    case 6: digitalWrite(PIN_SERVO2, on ? HIGH : LOW); break;
    case 7: digitalWrite(PIN_SERVO3, on ? HIGH : LOW); break;
    default: break;
  }
}

// 하위 호환(I2C/기존 UART "F,<mask>")용: FAN 3비트 마스크
static void applyFanMask(uint8_t mask) {
  const uint8_t m = (uint8_t)(mask & 0x07);
  applyRemoteOut(0, (m & 0x01) != 0);
  applyRemoteOut(2, (m & 0x02) != 0);
  applyRemoteOut(3, (m & 0x04) != 0);
}

// 하위 호환(I2C "PUMP mask")용: SERVO 4비트 마스크
static void applyPumpMask(uint8_t mask) {
  const uint8_t m = (uint8_t)(mask & 0x0F);
  applyRemoteOut(4, (m & 0x01) != 0);
  applyRemoteOut(5, (m & 0x02) != 0);
  applyRemoteOut(6, (m & 0x04) != 0);
  applyRemoteOut(7, (m & 0x08) != 0);
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
static const uint32_t PANEL_LINK_BAUD = 19200;
#define PANEL_LINK_SERIAL Serial1

// I2C 점검: R4(requestFrom) 호출 여부/횟수
static volatile uint32_t gI2cReqCount = 0;
static volatile uint32_t gI2cLastReqMs = 0;

static void qPush(uint8_t t, uint8_t p) {
  // UART 링크는 실사용 경로이므로 큐 포화와 무관하게 항상 전송합니다.
  PANEL_LINK_SERIAL.print("v=1;type=evt;t=");
  PANEL_LINK_SERIAL.print((unsigned)t);
  PANEL_LINK_SERIAL.print(";p=");
  PANEL_LINK_SERIAL.println((unsigned)p);

  // I2C 하위호환 큐는 여유가 있을 때만 적재합니다.
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

static void lcdWriteText(uint8_t row, const char* s) {
  char b[20];
  for (uint8_t i = 0; i < 20; i++) b[i] = ' ';
  if (s) {
    const size_t n = strlen(s);
    for (uint8_t i = 0; i < 20 && i < n; i++) b[i] = s[i];
  }
  lcdWriteLine20(row, b);
}

static void lcdShowBootMessage() {
  // "LCD판넬 부팅메세지"(정의)
  // 요청 사양: 0/1행만 갱신, 2/3행은 유지
  lcd.clear();
  delay(5);
  lcdWriteText(0, "CronusFarm Panel");
  lcdWriteText(1, "UART ready");
}

static void lcdReinitIfNeeded(uint32_t nowMs, bool masterOwnsLcd) {
  // 전원/노이즈로 LCD 컨트롤러만 리셋되면 "흰색 두 줄" 상태가 될 수 있어
  // 일정 주기마다 최소 재초기화를 수행해 자동 복구를 시도합니다.
  if (masterOwnsLcd) {
    return;
  }
  // 마스터(R4)가 UART로 계속 라인을 보내는 동안엔 재초기화가 깜박임을 유발할 수 있어 스킵합니다.

  // 초기화는 너무 자주 하면 화면이 깜박일 수 있으니 간격을 늘립니다.
  if (nowMs - gLastLcdInitMs < 30000) {
    return;
  }
  gLastLcdInitMs = nowMs;
  lcd.begin(20, 4);
  delay(5);
  if (!gWelcomeShown) {
    lcdShowBootMessage();
  } else {
    // 마스터가 곧 다시 덮어쓸 수 있으나, LCD 리셋 직후에는 현재 welcome 정보를 복구해 깜박임을 줄입니다.
    lcdWriteText(0, "Welcome 2 CronusFarm");
    lcdWriteText(1, gDateLine);
    lcdWriteText(2, gTimeLine);
    lcdWriteText(3, "");
  }
}

static void lcdShowWelcomeMessage() {
  // "LCD판넬 환영메세지"(압축형)
  lcd.clear();
  lcdWriteText(0, "Welcome 2 CronusFarm");
  lcdWriteText(1, gDateLine);
  lcdWriteText(2, gTimeLine);
  // 3행은 비움(요청: 환영 3줄만 표시)
  lcdWriteText(3, "");
  gWelcomeShown = true;
}

static void serialTimePoll() {
  // 라인 단위 파서(최대 79B). CR/LF 모두 허용.
  static char line[80];
  static uint8_t len = 0;

  while (Serial.available() > 0) {
    const char c = (char)Serial.read();
    if (c == '\r' || c == '\n') {
      if (len == 0) continue;
      line[len] = '\0';
      if (strncmp(line, "DT:", 3) == 0) {
        const char* v = line + 3;
        snprintf(gDateLine, sizeof(gDateLine), "%-20.20s", v);
      } else if (strncmp(line, "TM:", 3) == 0) {
        const char* v = line + 3;
        snprintf(gTimeLine, sizeof(gTimeLine), "%-20.20s", v);
      }
      len = 0;
      continue;
    }
    if (len < (uint8_t)(sizeof(line) - 1)) {
      line[len++] = c;
    }
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
static bool gUartMasterActive = false;

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

    if (op == PANEL_CMD_SET_FANS) {
      if ((uint8_t)(rlen - i) < 1) {
        break;
      }
      uint8_t mask = rx[i++];
#if defined(ARDUINO_AVR_MEGA2560) || defined(ARDUINO_AVR_MEGA)
      applyFanMask(mask);
#endif
      continue;
    }

    break;
  }
}

static void processUartMasterRx() {
  static char line[96];
  static uint8_t len = 0;
  while (PANEL_LINK_SERIAL.available() > 0) {
    const char c = (char)PANEL_LINK_SERIAL.read();
    if (c == '\r' || c == '\n') {
      if (len == 0) continue;
      line[len] = '\0';
      len = 0;

      if (strcmp(line, "C") == 0) {
        gSawLcdCmd = true;
        gLastLcdCmdMs = millis();
        gUartMasterActive = true;
        lcd.clear();
        continue;
      }
      // R4 → Mega LCD 라인 명령 포맷: "L,<row>,<text>\n"
      // 초기 동작(완화 파싱) 복원: 문자열 프레이밍이 약간 어긋나도 화면 갱신이 끊기지 않게 합니다.
      if (line[0] == 'L' && line[1] == ',') {
        char* p1 = strchr(line + 2, ',');
        if (!p1) continue;
        *p1 = '\0';
        int row = atoi(line + 2);
        if (row < 0) row = 0;
        if (row > 3) row = 3;
        gSawLcdCmd = true;
        gLastLcdCmdMs = millis();
        gUartMasterActive = true;
        lcdWriteText((uint8_t)row, p1 + 1);
        continue;
      }
      // R4 → Mega "반전(유사)" 표시: 커서 블링크로 강조
      // 포맷: "H,<row>,<col>,<0|1>\n"
      // - on=1: 해당 위치로 커서를 옮기고 blink on
      // - on=0: blink off (커서도 숨김)
      if (line[0] == 'H' && line[1] == ',') {
        char* p1 = strchr(line + 2, ',');
        if (!p1) continue;
        *p1 = '\0';
        char* p2 = strchr(p1 + 1, ',');
        if (!p2) continue;
        *p2 = '\0';
        int row = atoi(line + 2);
        int col = atoi(p1 + 1);
        const int on = atoi(p2 + 1);
        if (row < 0) row = 0;
        if (row > 3) row = 3;
        if (col < 0) col = 0;
        if (col > 19) col = 19;
        gSawLcdCmd = true;
        gLastLcdCmdMs = millis();
        gUartMasterActive = true;
        if (on) {
          lcd.setCursor((uint8_t)col, (uint8_t)row);
          lcd.cursor();
          lcd.blink();
        } else {
          lcd.noBlink();
          lcd.noCursor();
        }
        continue;
      }
      // R4 → Mega 비프 명령 포맷: "B,<0|1>\n"
      if (line[0] == 'B' && line[1] == ',') {
        const int mode = atoi(line + 2);
        if (mode == 0) beepShortLocal();
        else beepLongLocal();
        gSawLcdCmd = true;
        gLastLcdCmdMs = millis();
        gUartMasterActive = true;
        continue;
      }
      // R4 → Mega 팬 마스크 포맷: "F,<0..7>\n"
      if (line[0] == 'F' && line[1] == ',') {
#if defined(ARDUINO_AVR_MEGA2560) || defined(ARDUINO_AVR_MEGA)
        applyFanMask((uint8_t)(atoi(line + 2) & 0x07));
#endif
        gSawLcdCmd = true;
        gLastLcdCmdMs = millis();
        gUartMasterActive = true;
        continue;
      }
      // R4 → Mega 원격 GPIO 포맷: "O,<idx>,<0|1>\n"
      // - idx: 0..7 (FAN A1/A2/B1/B2, SERVO0~3)
      if (line[0] == 'O' && line[1] == ',') {
#if defined(ARDUINO_AVR_MEGA2560) || defined(ARDUINO_AVR_MEGA)
        char* p1 = strchr(line + 2, ',');
        if (!p1) continue;
        *p1 = '\0';
        const int idx = atoi(line + 2);
        const int v = atoi(p1 + 1);
        if (idx >= 0 && idx <= 7) {
          applyRemoteOut((uint8_t)idx, v ? true : false);
        }
#endif
        gSawLcdCmd = true;
        gLastLcdCmdMs = millis();
        gUartMasterActive = true;
        continue;
      }
      continue;
    }
    if (len < (uint8_t)(sizeof(line) - 1)) {
      line[len++] = c;
    }
  }
}

static int8_t gEncPrevAB = 0;
static uint32_t gEncLastMs = 0;
static int8_t gEncPrevA = -1;
static int8_t gEncPrevB = -1;
// 엔코더 민감도(누적 스텝 수). 값이 클수록 “더 많이 돌려야” 이벤트가 1번 발생합니다.
  // Mega(Trigorilla)에서는 7이면 체감상 거의 안 움직이는 경우가 있어 상대적으로 낮춤.
#if defined(ARDUINO_AVR_MEGA2560) || defined(ARDUINO_AVR_MEGA)
static const int8_t ENC_STEPS_PER_EVENT = 3;
#else
static const int8_t ENC_STEPS_PER_EVENT = 7;
#endif
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
  pinMode(PIN_FAN_A1, OUTPUT);
  pinMode(PIN_FAN_A2, OUTPUT);
  pinMode(PIN_FAN_B1, OUTPUT);
  pinMode(PIN_FAN_B2, OUTPUT);
  pinMode(PIN_SERVO0, OUTPUT);
  pinMode(PIN_SERVO1, OUTPUT);
  pinMode(PIN_SERVO2, OUTPUT);
  pinMode(PIN_SERVO3, OUTPUT);
  for (uint8_t i = 0; i < 8; i++) {
    applyRemoteOut(i, false);
  }

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

  Serial.begin(115200);
  PANEL_LINK_SERIAL.begin(PANEL_LINK_BAUD);

  lcd.begin(20, 4);
  delay(50);  // HD44780 전원 안정·초기화 여유
  gLastLcdInitMs = millis();
  lcdShowBootMessage();

  SPI.begin();
  if (SD.begin(PIN_SD_CS)) {
    lcd.setCursor(0, 2);
    lcd.print("SD: OK           ");
  } else {
    lcd.setCursor(0, 2);
    lcd.print("SD: (no/fail)    ");
  }

  // Pi 부팅 시간 동안(정의된 "LCD판넬 부팅메세지")을 잠깐 유지합니다.

  // UART 링크를 기본으로 사용합니다. I2C 슬레이브는 하위 호환을 위해 남겨둡니다.
  Wire.begin(PANEL_I2C_ADDR);
  Wire.onReceive(onReceiveHandler);
  Wire.onRequest(onRequestHandler);

  gBootAtMs = millis();
}

void loop() {
  processUartMasterRx();
  processI2cMasterRx();
  serialTimePoll();
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
  // R4가 이벤트만 poll(requestFrom)하는 동안에도 로컬 환영 3줄이 덮어쓰면 안 됨
  // L만 오다가 O/F/B만 연속으로 올 때도 로컬 LCD 간섭을 막기 위해 창을 넉넉히 잡습니다.
  const bool masterCmdRecent = gSawLcdCmd && (now - gLastLcdCmdMs) < 5000;
  const bool masterPollRecent =
    (gI2cReqCount > 0u) && (gI2cLastReqMs != 0u) && ((now - gI2cLastReqMs) < 3000u);
  const bool masterOwnsLcd = masterCmdRecent || masterPollRecent;
  lcdReinitIfNeeded(now, masterOwnsLcd);

  // 부팅메세지(5초) 후 환영메세지로 전환(단, R4가 LCD를 잡기 시작하면 자동 전환 금지)
  if (!gWelcomeShown && !masterOwnsLcd && (now - gBootAtMs) >= BOOT_MSG_MS) {
    lcdShowWelcomeMessage();
  }

  // 환영메세지가 표시된 상태에서는 Pi 시간 수신 시 1/2행(날짜/시간)만 갱신
  // 단, R4(UART)가 LCD를 제어하기 시작하면(=gUartMasterActive) 로컬 시간 갱신은 중단(잔상/깨짐 원인)
  if (gWelcomeShown && !masterOwnsLcd) {
    static uint32_t lastWelcomeUi = 0;
    static char lastDate[21] = {0};
    static char lastTime[21] = {0};
    // 날짜/시간은 1초 단위로만 갱신(깜박임 감소)
    if (now - lastWelcomeUi >= 1000) {
      lastWelcomeUi = now;
      if (strncmp(lastDate, gDateLine, 20) != 0) {
        strncpy(lastDate, gDateLine, 20);
        lastDate[20] = '\0';
        lcdWriteText(1, gDateLine);
      }
      if (strncmp(lastTime, gTimeLine, 20) != 0) {
        strncpy(lastTime, gTimeLine, 20);
        lastTime[20] = '\0';
        lcdWriteText(2, gTimeLine);
      }
    }
  }

  // 부팅메세지 모드에서만 4행 디버그 출력(기존 동작 유지)
  if (!gWelcomeShown && !masterOwnsLcd && now - lastUi >= 500) {
    lastUi = now;
    lcd.setCursor(0, 3);
    // R4의 요청/명령 수신 여부를 함께 표시
    const uint32_t reqCnt = gI2cReqCount;
    const uint32_t ageMs = (gI2cLastReqMs == 0) ? 0xFFFFFFFFu : (now - gI2cLastReqMs);
    if (!gSawMasterCmd) {
      char b[21];
      if (ageMs == 0xFFFFFFFFu) {
        snprintf(b, sizeof(b), "PUMPS:0000 R%lu      ", (unsigned long)reqCnt);
      } else {
        snprintf(b, sizeof(b), "PUMPS:0000 R%lu %lums", (unsigned long)reqCnt, (unsigned long)ageMs);
      }
      lcd.print(b);
    } else {
      char b[21];
      // 디버그 표기(기존 4비트): SERVO0~3 상태를 PUMPS 자리로 표시(호환 유지)
      snprintf(b, sizeof(b), "PUMPS:%c%c%c%c R%lu    ",
               gRemoteOut[4] ? '1' : '0',
               gRemoteOut[5] ? '1' : '0',
               gRemoteOut[6] ? '1' : '0',
               gRemoteOut[7] ? '1' : '0',
               (unsigned long)reqCnt);
      lcd.print(b);
    }
  }
#endif
}
