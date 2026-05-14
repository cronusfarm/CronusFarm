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
// 기본: EXP1-2→**D8**(ENC 클릭), EXP2 **6번→D13**(SD CS). EXP2-2는 리본 SPI선이면 D10에 풀업만(클릭 아님).
// 리본을 쉴드 표준대로(2→D13, 6→D10)만 꽂은 경우: 빌드 전 `#define CF_ENC_CLICK_USE_PIN 13` + `#define CF_SD_CS_USE_PIN 10`.
#ifndef CF_ENC_CLICK_USE_PIN
#define CF_ENC_CLICK_USE_PIN 8
#endif
#ifndef CF_SD_CS_USE_PIN
#define CF_SD_CS_USE_PIN 13
#endif
// 0=눌림 시 LOW(GND, INPUT_PULLUP 기본). 1=눌림 시 HIGH(외부 풀다운 등 배선에 맞출 것).
#ifndef CF_ENC_CLICK_ACTIVE_HIGH
#define CF_ENC_CLICK_ACTIVE_HIGH 0
#endif
#ifndef CF_ENC_CLICK_DEBOUNCE_MS
#define CF_ENC_CLICK_DEBOUNCE_MS 220
#endif
// 리본 물리 3·5 → UNO: 정본은 3→A0(ENC A), 5→A1(ENC B). **3→A1·5→A0** 으로 납댄 현장이면 1.
#ifndef CF_ENC_AB_SWAP
#define CF_ENC_AB_SWAP 0
#endif
// 클릭 핀 변경 시: EXP1(LCD)은 D2~D7만 사용. D8 클릭 OK. A2/A3는 `CF_R3_PANEL_UART_LINK==1`일 때만 UART. I2C A4/A5 금지.

// 부저 및 엔코더 방향 설정[cite: 2]
#define CF_PANEL_HAS_BEEPER 1
static const int8_t CF_ENC_DIR = +1;

// EXP2 리본 6번→D13(CS). 클릭은 EXP1-2→D8(EXP2-2와 **납선으로 잇지 않아도 됨** — 같은 네트일 때만 자동 연결).
// EXP1(현장 BTT 2004A): 1번=부저→D9(타단 VCC·보통 10번), 2번=BTN_ENC→D8, 3~8=LCD→D7~D2, 9=GND, 10=5V — docs §3.2.1
static const int PIN_BEEPER = 9;
static const int PIN_LCD_RS = 6;
static const int PIN_LCD_EN = 7;
static const int PIN_LCD_D4 = 5;
static const int PIN_LCD_D5 = 4;
static const int PIN_LCD_D6 = 3;
static const int PIN_LCD_D7 = 2;
static const int PIN_SD_CS = CF_SD_CS_USE_PIN;   // SD 미사용 시 OUTPUT HIGH
#if CF_ENC_AB_SWAP
static const int PIN_ENC_A = A1;
static const int PIN_ENC_B = A0;
#else
static const int PIN_ENC_A = A0;     // EXP2 물리 3 → A0
static const int PIN_ENC_B = A1;     // EXP2 물리 5 → A1
#endif
static const int PIN_ENC_CLICK = CF_ENC_CLICK_USE_PIN;
static const int PIN_SD_DET = -1;
static const int PIN_KILL = -1;

LiquidCrystal lcd(PIN_LCD_RS, PIN_LCD_EN, PIN_LCD_D4, PIN_LCD_D5, PIN_LCD_D6, PIN_LCD_D7);

// UART(R4 Serial1↔R3) — 패널은 I2C만 쓰면 0 유지(배선 없음). 1이면 R3 A2/A3 SoftwareSerial 사용
#define CF_R3_PANEL_UART_LINK 0
static const int PIN_UART_RX = A2;
static const int PIN_UART_TX = A3;
static SoftwareSerial gUart(PIN_UART_RX, PIN_UART_TX);
static char gUartLine[96];
static uint8_t gUartLen = 0;
static const uint32_t CF_UART_BAUD = 9600;
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

struct QueEvt {
  uint8_t t;
  uint8_t p;
};
#define PANEL_Q_CAP 16
#define PANEL_I2C_EVT_MAX 14
static QueEvt gQ[PANEL_Q_CAP];
static uint8_t gQLen = 0;
static uint32_t gLastEvtTxMs = 0;

static volatile uint32_t gI2cReqCount = 0;
static volatile uint32_t gI2cLastReqMs = 0;
static volatile bool gI2cRxPending = false;
static uint8_t gI2cRxLen = 0;
static uint8_t gI2cRxBuf[32];
static bool gSawLcdCmd = false;
static uint32_t gLastLcdCmdMs = 0;
static bool gMasterEverOwned = false;

// ============================================================
// 이벤트 큐 및 부저 함수[cite: 2]
static void qPush(uint8_t t, uint8_t p) {
  if (gQLen >= PANEL_Q_CAP) return;
  gQ[gQLen].t = t;
  gQ[gQLen].p = p;
  gQLen++;
}

// 클릭은 Edit 진입용이라 큐가 꽉 차면 뒤에서부터 엔코더 이벤트를 버려 공간 확보
static void qPushClick(uint8_t p) {
  while (gQLen >= PANEL_Q_CAP) {
    if (gQLen == 0) return;
    const uint8_t bt = gQ[gQLen - 1].t;
    if (bt == PANEL_EVT_ENC_CW || bt == PANEL_EVT_ENC_CCW) {
      gQLen--;
    } else {
      break;
    }
  }
  if (gQLen >= PANEL_Q_CAP) return;
  gQ[gQLen].t = PANEL_EVT_CLICK;
  gQ[gQLen].p = p;
  gQLen++;
}

static void uartSendQueuedEvents() {
  // SoftwareSerial은 RX/TX를 동시에 잘 못합니다.
  // LCD 명령 수신 중 즉시 TX 하면 바이트 유실이 커져 입력(엔코더)이 먹통처럼 보일 수 있어,
  // "수신이 잠깐 끊긴 틈"에만 이벤트를 1개씩 보냅니다.
  if (!CF_R3_PANEL_UART_LINK) return;
  if (gQLen == 0) return;
  // L,... 한 줄을 조립하는 도중이거나 RX FIFO에 바이트가 남아 있으면 절대 TX 금지
  // (그렇지 않으면 3·4행 CH/힌트만 깨지고 1·2행은 상대적으로 멀쩡해 보이는 현상이 납니다)
  if (gUartLen > 0) return;
  if (gUart.available() > 0) return;

  const uint32_t now = millis();
  if (gUartLastByteMs != 0 && (now - gUartLastByteMs) < 10) return;
  if (gLastEvtTxMs != 0 && (now - gLastEvtTxMs) < 10) return;
  gLastEvtTxMs = now;

  const QueEvt e = gQ[0];
  for (uint8_t i = 0; i + 1 < gQLen; i++) gQ[i] = gQ[i + 1];
  gQLen--;

  // 형식: E,<t>,<p>\n
  gUart.print("E,");
  gUart.print((unsigned)e.t);
  gUart.print(",");
  gUart.println((unsigned)e.p);
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
  gMasterEverOwned = true;
  uint8_t sendN = (gQLen > PANEL_I2C_EVT_MAX) ? PANEL_I2C_EVT_MAX : gQLen;
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
  lcdWriteText(1, "");
}

static void lcdShowWelcomeMessage() {
  lcd.clear();
  // 20×4 한 줄 20자 초과 시 잘림 — R3에는 RTC 갱신 없음(gDateLine/gTimeLine은 초기 플레이스홀더만)
  lcdWriteText(0, "Welcome to CronusFarm");
  lcdWriteText(1, gDateLine);
  lcdWriteText(2, gTimeLine);
  lcdWriteText(3, "");
  gWelcomeShown = true;
}

// ============================================================
// 입력 폴링 함수[cite: 2]
static void encoderPoll() {
  static int8_t gEncPrevAB = 0;
  static int8_t gEncPrevA = -1;
  static int8_t gEncPrevB = -1;
  static uint32_t gEncLastMs = 0;
  static int8_t gEncAccum = 0;
  static uint32_t sEncLastQueueMs = 0;
  // RepRap 엔코더는 델타당 1이면 한 칸에 CW 2번 이상 나가기 쉬움 → 4에 가깝게 1칸=1이벤트
  static const int8_t ENC_STEPS_PER_EVENT = 4;
  static const uint32_t ENC_QUEUE_MIN_MS = 48;

  uint32_t now = millis();
  if (now - gEncLastMs < 1) return;
  gEncLastMs = now;

  int a = digitalRead(PIN_ENC_A) ? 1 : 0;
  int b = digitalRead(PIN_ENC_B) ? 1 : 0;
  int8_t ab = (int8_t)((a << 1) | b);

  static const int8_t delta[16] = {0, 1, -1, 0, -1, 0, 0, 1, 1, 0, 0, -1, 0, -1, 1, 0};
  int8_t idx = (int8_t)((gEncPrevAB << 2) | ab);
  int8_t d = (int8_t)(delta[(uint8_t)idx] * CF_ENC_DIR);
  gEncPrevAB = ab;

  // 미세 스텝에서 delta가 0으로만 나오는 어댑터 보강(UI 시뮬 스케치와 동일 계열)
  if (gEncPrevA < 0 || gEncPrevB < 0) {
    gEncPrevA = (int8_t)a;
    gEncPrevB = (int8_t)b;
    return;
  }
  if (d == 0 && (a != gEncPrevA || b != gEncPrevB)) {
    if (a != gEncPrevA) {
      d = (int8_t)(((b == a) ? +1 : -1) * CF_ENC_DIR);
    } else {
      d = (int8_t)(((a != b) ? +1 : -1) * CF_ENC_DIR);
    }
  }
  gEncPrevA = (int8_t)a;
  gEncPrevB = (int8_t)b;

  if (d == 0) return;
  gEncAccum += d;
  if (gEncAccum > 12) {
    gEncAccum = 12;
  }
  if (gEncAccum < -12) {
    gEncAccum = -12;
  }
  if (gEncAccum >= ENC_STEPS_PER_EVENT) {
    uint32_t tq = millis();
    if (sEncLastQueueMs == 0u || (tq - sEncLastQueueMs) >= ENC_QUEUE_MIN_MS) {
      gEncAccum = 0;
      sEncLastQueueMs = tq;
      gEncCwCount++;
      qPush(PANEL_EVT_ENC_CW, 0);
    }
  } else if (gEncAccum <= -ENC_STEPS_PER_EVENT) {
    uint32_t tq = millis();
    if (sEncLastQueueMs == 0u || (tq - sEncLastQueueMs) >= ENC_QUEUE_MIN_MS) {
      gEncAccum = 0;
      sEncLastQueueMs = tq;
      gEncCcwCount++;
      qPush(PANEL_EVT_ENC_CCW, 0);
    }
  }
}

static void clickPoll() {
  static uint32_t gBtnLastMs = 0;
  static bool prevPressed = false;
  const bool rawHigh = (digitalRead(PIN_ENC_CLICK) == HIGH);
#if CF_ENC_CLICK_ACTIVE_HIGH
  const bool pressed = rawHigh;
#else
  const bool pressed = !rawHigh;
#endif
  // 이전 800µs 재확인은 바운스로 LOW가 풀리면 클릭 전체를 버려 EDIT 미진입 원인이 됨 → 엣지만 사용
  if (pressed && !prevPressed) {
    uint32_t now = millis();
    if (now - gBtnLastMs >= (uint32_t)CF_ENC_CLICK_DEBOUNCE_MS) {
      gBtnLastMs = now;
      gClickCount++;
      qPushClick(1);
      beepLongLocal();
    }
  }
  prevPressed = pressed;
}

// ============================================================
// 메인 루틴[cite: 2]
void setup() {
  pinMode(PIN_BEEPER, OUTPUT);
  // A4/A5는 R4와 I2C — 여기에 내부 풀업/출력 걸지 말 것
  pinMode(PIN_ENC_A, INPUT_PULLUP);
  pinMode(PIN_ENC_B, INPUT_PULLUP);
  pinMode(PIN_SD_CS, OUTPUT);
  digitalWrite(PIN_SD_CS, HIGH);
  pinMode(PIN_ENC_CLICK, INPUT_PULLUP);
  // EXP2-2 리본이 D10(MISO 등)로만 오고 클릭은 EXP1-2→D8일 때 D10 떠 있음 방지(CS가 D10이면 금지)
  if (PIN_ENC_CLICK != 10 && PIN_SD_CS != 10) pinMode(10, INPUT_PULLUP);
  // EXP2에서 엔코더에 안 쓰는 D11·D12(리본 4·1) — 떠 있으면 입력 고정
  pinMode(11, INPUT_PULLUP);
  pinMode(12, INPUT_PULLUP);

  Serial.begin(115200);
  beepShortLocal(); delay(80); beepShortLocal();

  lcd.begin(20, 4);
  lcdShowBootMessage();

  if (CF_R3_PANEL_UART_LINK) {
    gUart.begin(CF_UART_BAUD);
    gUart.listen();
  }

  Wire.begin(PANEL_I2C_ADDR);
  Wire.onReceive(onReceiveHandler);
  Wire.onRequest(onRequestHandler);
  gBootAtMs = millis();
}

void loop() {
  // 엔코더/클릭을 LCD I2C 처리보다 먼저(긴 SET_LINE 연속 시 샘플이 밀려 한 번에 여러 스텝이 쌓임)
  encoderPoll();
  clickPoll();

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

  if (CF_R3_PANEL_UART_LINK) {
  // UART 명령 처리 (R4가 LCD를 소유하는 경우)
  // 한 루프에 바이트를 무제한 읽으면 엔코더 폴링이 밀려 입력이 죽은 것처럼 보입니다.
  // 한 L, 명령은 약 25바이트; 4줄 연속이면 한 루프에서 최대한 비워 두면
  // gUartLen>0 상태로 encoder/uart TX 구간에 남을 확률이 줄어듦
  for (int uartBudget = 0; uartBudget < 120 && gUart.available() > 0; uartBudget++) {
    char c = (char)gUart.read();
    gUartLastByteMs = millis();
    // 일부 배선/노이즈 환경에서 '\n'이 유실되고 '\r'만 도착하는 케이스가 있어
    // '\r'도 라인 종료로 취급해 파서가 계속 굴러가게 합니다.
    if (c == '\r') c = '\n';
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
        gMasterEverOwned = true;
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
            gMasterEverOwned = true;
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
    // R4가 줄 사이에 ms급 휴지를 두므로, 너무 짧으면 정상 L,... 후반부를 버림
    if (gUartLastByteMs != 0 && (nowMs - gUartLastByteMs) > 200) {
      gUartLen = 0;
    }
  }
  }

  uartSendQueuedEvents();

  // 부팅 후 환영 메시지 전환[cite: 2]
  uint32_t now = millis();
  const bool masterOwnsLcd =
    ((gI2cReqCount > 0u) && ((now - gI2cLastReqMs) < 3000u)) ||
    (gSawLcdCmd && ((now - gLastLcdCmdMs) < 3000u));
  if (!gWelcomeShown && !masterOwnsLcd && !gMasterEverOwned && (now - gBootAtMs) >= BOOT_MSG_MS) {
    lcdShowWelcomeMessage();
  }
}