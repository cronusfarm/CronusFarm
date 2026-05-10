/*
  2026.05.06 17:36:00
  CronusFarm — UNO R3 패널 전용 (RepRapDiscount Smart Controller 2004A)
  역할: LCD / 엔코더 / 클릭 / 부저 / SD / KILL / SD 감지
  통신: I2C (Slave 0x38) - R4 WiFi(Master)와 연결
*/

#include <Wire.h>
#include <SPI.h>
#include <string.h>
#include <LiquidCrystal.h>
#include <SoftwareSerial.h>
#include "panel_i2c_protocol.h"

// R3 패널 전용 구성: SD 기능은 사용하지 않습니다.
#define CF_PANEL_HAS_SD 0

// 부저 및 엔코더 방향 설정[cite: 2]
#define CF_PANEL_HAS_BEEPER 1
static const int8_t CF_ENC_DIR = +1;

// ============================================================
// 핀 정의 (UNO R3 현장 배선 기준)[cite: 2]
static const int PIN_BEEPER = 9;
static const int PIN_ENC_CLICK = 8;
static const int PIN_LCD_RS = 6;
static const int PIN_LCD_EN = 7;
static const int PIN_LCD_D4 = 5;
static const int PIN_LCD_D5 = 4;
static const int PIN_LCD_D6 = 3;
static const int PIN_LCD_D7 = 2;
static const int PIN_ENC_A = A0;
static const int PIN_ENC_B = A1;
static const int PIN_SD_CS = 10;
static const int PIN_SD_DET = -1; 
static const int PIN_KILL = -1;   

LiquidCrystal lcd(PIN_LCD_RS, PIN_LCD_EN, PIN_LCD_D4, PIN_LCD_D5, PIN_LCD_D6, PIN_LCD_D7);

// ============================================================
// UART 링크 (R4 ↔ R3)
// - R3의 HW Serial(0/1)은 USB 업로드/디버그 전용으로 비워둡니다.
// - 통신은 SoftwareSerial로 별도 핀 사용(업로드 충돌 방지).
// - 주의: RepRapDiscount 2004A 패널의 EXP2는 보통 D10~D13(SPI/SD) 라인을 씁니다.
//   따라서 UART는 EXP2와 겹치지 않는 A2/A3(디지털 16/17)을 사용합니다.
static const int PIN_UART_RX = A2; // (D16) R4 TX1(핀 1) → R3 RX
static const int PIN_UART_TX = A3; // (D17) R4 RX1(핀 0) ← R3 TX
static SoftwareSerial gUart(PIN_UART_RX, PIN_UART_TX);
static char gUartLine[96];
static uint8_t gUartLen = 0;
static const uint32_t CF_UART_BAUD = 19200;
static uint32_t gUartLastByteMs = 0;

// ============================================================
// 상태 변수
static char gDateLine[21] = "----.--.-- (---)   ";
static char gTimeLine[21] = "--:--:--            ";
static bool gWelcomeShown = false;
static uint32_t gBootAtMs = 0;
static const uint32_t BOOT_MSG_MS = 10000;
static uint32_t gLastLcdInitMs = 0;
static uint32_t gEncCwCount = 0;
static uint32_t gEncCcwCount = 0;
static uint32_t gClickCount = 0;
static uint32_t gLastDbgDrawMs = 0;

struct QueEvt {
  uint8_t t;
  uint8_t p;
};
static QueEvt gQ[8];
static uint8_t gQLen = 0;

static volatile uint32_t gI2cReqCount = 0;
static volatile uint32_t gI2cLastReqMs = 0;
static volatile bool gI2cRxPending = false;
static uint8_t gI2cRxLen = 0;
static uint8_t gI2cRxBuf[32];
static bool gSawLcdCmd = false;
static uint32_t gLastLcdCmdMs = 0;

// ============================================================
// 이벤트 큐 및 부저 함수[cite: 2]
static void qPush(uint8_t t, uint8_t p) {
  if (gQLen >= 8) return;
  gQ[gQLen].t = t;
  gQ[gQLen].p = p;
  gQLen++;

  // UART 실시간 이벤트(엔코더/클릭)를 R4로 즉시 전달합니다.
  // 형식: E,<t>,<p>\n
  gUart.print("E,");
  gUart.print((unsigned)t);
  gUart.print(",");
  gUart.println((unsigned)p);
}

static void beepShortLocal() {
  if (!CF_PANEL_HAS_BEEPER) return;
  for (int i = 0; i < 80; i++) {
    digitalWrite(PIN_BEEPER, HIGH); delayMicroseconds(125);
    digitalWrite(PIN_BEEPER, LOW);  delayMicroseconds(125);
  }
}

static void beepLongLocal() {
  if (!CF_PANEL_HAS_BEEPER) return;
  for (int i = 0; i < 400; i++) {
    digitalWrite(PIN_BEEPER, HIGH); delayMicroseconds(125);
    digitalWrite(PIN_BEEPER, LOW);  delayMicroseconds(125);
  }
}

// ============================================================
// I2C 핸들러[cite: 2]
void onRequestHandler() {
  gI2cReqCount++;
  gI2cLastReqMs = millis();
  uint8_t sendN = (gQLen > 7) ? 7 : gQLen;
  Wire.write(sendN);
  for (uint8_t i = 0; i < sendN; i++) {
    Wire.write(gQ[i].t);
    Wire.write(gQ[i].p);
  }
  uint8_t left = (uint8_t)(gQLen - sendN);
  for (uint8_t i = 0; i < left; i++) gQ[i] = gQ[i + sendN];
  gQLen = left;
}

void onReceiveHandler(int numBytes) {
  uint8_t n = 0;
  while (Wire.available() && n < (uint8_t)sizeof(gI2cRxBuf)) {
    gI2cRxBuf[n++] = (uint8_t)Wire.read();
  }
  if (n > 0) {
    gI2cRxLen = n;
    gI2cRxPending = true;
  }
}

// ============================================================
// LCD 출력 함수[cite: 2]
static void lcdWriteLine20(uint8_t row, const char line20[20]) {
  lcd.setCursor(0, row);
  for (uint8_t i = 0; i < 20; i++) lcd.write((uint8_t)line20[i]);
}

static void lcdWriteText(uint8_t row, const char* s) {
  char b[20];
  for (uint8_t i = 0; i < 20; i++) b[i] = ' ';
  if (s) {
    size_t n = strlen(s);
    for (uint8_t i = 0; i < 20 && i < n; i++) b[i] = s[i];
  }
  lcdWriteLine20(row, b);
}

static void lcdShowBootMessage() {
  lcd.clear();
  lcdWriteText(0, "CronusFarm Panel");
  lcdWriteText(1, "LINK:UART+I2C");
}

static void lcdShowWelcomeMessage() {
  lcd.clear();
  lcdWriteText(0, "Welcome 2 CronusFarm");
  lcdWriteText(1, gDateLine);
  lcdWriteText(2, gTimeLine);
  lcdWriteText(3, "");
  gWelcomeShown = true;
}

// ============================================================
// 입력 폴링 함수[cite: 2]
static void encoderPoll() {
  static int8_t gEncPrevAB = 0;
  static uint32_t gEncLastMs = 0;
  static int8_t gEncAccum = 0;
  static const int8_t ENC_STEPS_PER_EVENT = 7;

  uint32_t now = millis();
  if (now - gEncLastMs < 2) return;
  gEncLastMs = now;

  int a = digitalRead(PIN_ENC_A) ? 1 : 0;
  int b = digitalRead(PIN_ENC_B) ? 1 : 0;
  int8_t ab = (int8_t)((a << 1) | b);

  static const int8_t delta[16] = {0, 1, -1, 0, -1, 0, 0, 1, 1, 0, 0, -1, 0, -1, 1, 0};
  int8_t idx = (int8_t)((gEncPrevAB << 2) | ab);
  int8_t d = (int8_t)(delta[(uint8_t)idx] * CF_ENC_DIR);
  gEncPrevAB = ab;

  if (d == 0) return;
  gEncAccum += d;
  if (gEncAccum >= ENC_STEPS_PER_EVENT) {
    gEncAccum = 0;
    gEncCwCount++;
    beepShortLocal();
    qPush(PANEL_EVT_ENC_CW, 0);
  } else if (gEncAccum <= -ENC_STEPS_PER_EVENT) {
    gEncAccum = 0;
    gEncCcwCount++;
    beepShortLocal();
    qPush(PANEL_EVT_ENC_CCW, 0);
  }
}

static void clickPoll() {
  static uint32_t gBtnLastMs = 0;
  static bool gBtnPrev = true;
  bool cur = digitalRead(PIN_ENC_CLICK);
  if (gBtnPrev && !cur) {
    uint32_t now = millis();
    if (now - gBtnLastMs > 220) {
      gBtnLastMs = now;
      gClickCount++;
      beepLongLocal();
      qPush(PANEL_EVT_CLICK, 1);
    }
  }
  gBtnPrev = cur;
}

// ============================================================
// 메인 루틴[cite: 2]
void setup() {
  pinMode(PIN_BEEPER, OUTPUT);
  pinMode(PIN_ENC_CLICK, INPUT_PULLUP);
  pinMode(PIN_ENC_A, INPUT_PULLUP);
  pinMode(PIN_ENC_B, INPUT_PULLUP);

  Serial.begin(115200);
  beepShortLocal(); delay(80); beepShortLocal();

  lcd.begin(20, 4);
  lcdShowBootMessage();

  gUart.begin(CF_UART_BAUD);
  gUart.listen();

  Wire.begin(PANEL_I2C_ADDR);
  Wire.onReceive(onReceiveHandler);
  Wire.onRequest(onRequestHandler);
  gBootAtMs = millis();
}

void loop() {
  // I2C 명령 처리[cite: 2]
  if (gI2cRxPending) {
    noInterrupts();
    uint8_t rx[32]; memcpy(rx, gI2cRxBuf, gI2cRxLen);
    uint8_t rlen = gI2cRxLen; gI2cRxPending = false;
    interrupts();

    uint8_t i = 0;
    while (i < rlen) {
      uint8_t op = rx[i++];
      if (op == PANEL_CMD_CLEAR) {
        gSawLcdCmd = true; gLastLcdCmdMs = millis(); lcd.clear();
      } else if (op == PANEL_CMD_SET_LINE) {
        uint8_t row = rx[i++]; uint8_t len = rx[i++];
        char line20[20]; memset(line20, ' ', 20);
        for (uint8_t k = 0; k < len && k < 20; k++) line20[k] = (char)rx[i + k];
        i += len; gSawLcdCmd = true; gLastLcdCmdMs = millis(); lcdWriteLine20(row, line20);
      } else if (op == PANEL_CMD_BEEP) {
        uint8_t m = rx[i++]; if (m == 0) beepShortLocal(); else beepLongLocal();
      }
    }
  }

  // UART 명령 처리 (R4가 LCD를 소유하는 경우)
  while (gUart.available() > 0) {
    char c = (char)gUart.read();
    gUartLastByteMs = millis();
    if (c == '\r') continue;
    if (c == '\n') {
      if (gUartLen == 0) continue;
      gUartLine[gUartLen] = '\0';
      gUartLen = 0;

      // 프로토콜:
      // - C
      // - L,<row>,<20chars>
      // - B,<0|1>
      if (gUartLine[0] == 'C' && gUartLine[1] == '\0') {
        gSawLcdCmd = true;
        gLastLcdCmdMs = millis();
        lcd.clear();
      } else if (gUartLine[0] == 'B' && gUartLine[1] == ',') {
        int m = -1;
        if (sscanf(gUartLine, "B,%d", &m) == 1) {
          if (m == 0) beepShortLocal(); else beepLongLocal();
        }
      } else if (gUartLine[0] == 'L' && gUartLine[1] == ',') {
        int row = -1;
        // "L,<row>,"
        char* p = strchr(gUartLine, ',');
        if (p) {
          row = atoi(p + 1);
          p = strchr(p + 1, ',');
          if (p && row >= 0 && row <= 3) {
            char line20[20];
            memset(line20, ' ', 20);
            const char* s = p + 1;
            for (uint8_t i = 0; i < 20 && s[i] != '\0'; i++) line20[i] = s[i];
            gSawLcdCmd = true;
            gLastLcdCmdMs = millis();
            lcdWriteLine20((uint8_t)row, line20);
          }
        }
      }
      continue;
    }
    // SoftwareSerial은 잡음/유실이 있으면 '\n'을 놓치고 버퍼가 꽉 차면서 "영구 먹통"이 될 수 있어
    // 오버플로 시 버퍼를 강제로 초기화합니다(다음 라인부터 재동기화).
    if (gUartLen >= (uint8_t)(sizeof(gUartLine) - 1)) {
      gUartLen = 0;
    }
    gUartLine[gUartLen++] = c;
  }

  // '\n'을 놓친 경우를 대비한 타임아웃 리셋(재동기화)
  if (gUartLen > 0) {
    uint32_t nowMs = millis();
    if (gUartLastByteMs != 0 && (nowMs - gUartLastByteMs) > 60) {
      gUartLen = 0;
    }
  }

  encoderPoll();
  clickPoll();

  // 부팅 후 환영 메시지 전환[cite: 2]
  uint32_t now = millis();
  const bool masterOwnsLcd =
    ((gI2cReqCount > 0u) && ((now - gI2cLastReqMs) < 3000u)) ||
    (gSawLcdCmd && ((now - gLastLcdCmdMs) < 3000u));
  if (!gWelcomeShown && !masterOwnsLcd && (now - gBootAtMs) >= BOOT_MSG_MS) {
    lcdShowWelcomeMessage();
  }

  // 디버그: 엔코더/클릭이 R3 내부에서 잡히는지 LCD 4번째 줄에 표시
  // - R4가 LCD를 소유(masterOwnsLcd)해도, 카운터 표시가 계속 갱신되면 "입력은 정상"입니다.
  if ((now - gLastDbgDrawMs) >= 250) {
    gLastDbgDrawMs = now;
    char b[21];
    // 20자 제한: "ENC+12 -34 C7"
    snprintf(b, sizeof(b), "ENC+%lu -%lu C%lu",
             (unsigned long)gEncCwCount,
             (unsigned long)gEncCcwCount,
             (unsigned long)gClickCount);
    lcdWriteText(3, b);
  }
}