/*
  CronusFarm — UNO R3 패널 전용 (RepRapDiscount Smart Controller 2004A)

  역할: LCD / 엔코더 / 클릭 / 부저 / SD / KILL / SD 감지
  통신: I2C 슬레이브 (마스터는 UNO R4 WiFi), SDA=A4 SCL=A5

  EXP1 → R3
    BEEPER A0, BTN_ENC A1, LCD EN D3, LCD RS D2, LCD D4~D7 → D4~D7
  EXP2 → R3
    SD MISO D12, SCK D13, ENC1 D8, SD CS D10, ENC2 D9, MOSI D11
    SD DETECT A2, KILL A3
*/

#include <Wire.h>
#include <SPI.h>
#include <SD.h>
#include <LiquidCrystal.h>
#include "panel_i2c_protocol.h"

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

static LiquidCrystal lcd(PIN_LCD_RS, PIN_LCD_EN, PIN_LCD_D4, PIN_LCD_D5, PIN_LCD_D6, PIN_LCD_D7);

struct QueEvt {
  uint8_t t;
  uint8_t p;
};
static QueEvt gQ[8];
static uint8_t gQLen = 0;

static void qPush(uint8_t t, uint8_t p) {
  if (gQLen >= 8) {
    return;
  }
  gQ[gQLen].t = t;
  gQ[gQLen].p = p;
  gQLen++;
}

static void onRequestHandler() {
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

static void onReceiveHandler(int /*numBytes*/) {
  // Wire 버퍼가 중간에 끊기면 다음 바이트가 op로 오해되어 화면이 깨질 수 있어
  // 수신 내용을 한 번에 버퍼링한 뒤 안전하게 파싱합니다.
  uint8_t rx[32];
  uint8_t rlen = 0;
  while (Wire.available() && rlen < (uint8_t)sizeof(rx)) {
    rx[rlen++] = (uint8_t)Wire.read();
  }

  uint8_t i = 0;
  while (i < rlen) {
    uint8_t op = rx[i++];
    if (op == PANEL_CMD_CLEAR) {
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

    // 알 수 없는 op: 남은 바이트는 폐기(동기화 목적)
    break;
  }
}

static int8_t gEncPrevAB = 0;
static uint32_t gEncLastMs = 0;

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
  if (d > 0) {
    qPush(PANEL_EVT_ENC_CW, 0);
  } else if (d < 0) {
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
  encoderPoll();
  clickPoll();
  killPoll();
  sdDetectPoll();
}
