/*
  2026.4.26 수정
  CronusFarm - UNO R4 WiFi (메인 MQTT·릴레이·I2C 마스터)
  패널(RepRap 2004A)은 UNO R3 `CronusFarmPanel` 스케치 — 별도 업로드

  목표
  - Node-RED(UI/자동화) ↔ Arduino 통신을 **MQTT(WiFi)** 로 전환
  - USB Serial은 업로드/디버그 용도로만 사용(포트 점유 충돌 최소화)

  토픽 규약(DEVICE_ID=cronusfarm-01 예시)
  - 명령 수신:   cronusfarm/cronusfarm-01/cmd
  - 상태 발행:   cronusfarm/cronusfarm-01/tele
  - 온라인 발행: cronusfarm/cronusfarm-01/status  (online/offline)
  - Pi SSID 동기: MQTT_TOPIC_PI_WIFI_SSID — `SSID` 또는 `SSID 비밀번호`(첫 공백 기준, 목록 외 등록)

  페이로드(간단/라이브러리 최소화)
  - cmd:  아래 2가지 형식을 모두 지원
    1) 단일 문자 명령(Serial 코드 호환): "M", "m", "A", "a", "B", "b", "C", "c", "N30", "F90"
    2) key=value 토큰(공백 구분): "auto=1 b1=0 b2=1 led=1 on=30 off=90"
  - tele: "S:... | A:... | T:... | W:ssid=... ip=a.b.c.d" (채널 상태 + WiFi 정보)

  핀(UNO R4 WiFi 메인 — 패널은 별도 UNO R3 I2C 슬레이브)
  - I2C 마스터: SDA A4, SCL A5 → R3 패널(슬레이브 0x38)
  - A Bed: LED_A1 D2, LED_A2 D3, PUMP_A1 D4, PUMP_A2 D5
  - B Bed: LED_B1 D6, PUMP_B1 D7, PUMP_B2 D8
  - D9~D13: 예비 / SPI 확장 비움 권장

  내장 LED 매트릭스(12x8)
  - WiFi만 연결: 고정 비트맵(사용자 지정 W 형태)
  - WiFi+MQTT 연결: 고정 비트맵(사용자 지정 WM 하단)
  - WiFi 끊김: 경고 패턴만 (펌프/LED는 매트릭스에 표시하지 않음)
*/

#include "RTC.h"
#include <EEPROM.h>
#include <WiFiS3.h>
#include <ArduinoMqttClient.h>
#include <string.h>
#include <stdio.h>
#include "Arduino_LED_Matrix.h"
#include "panel_protocol.h"
// `secrets.h.example`을 복사해서 `secrets.h`를 만든 뒤 값을 채우세요.
#include "secrets.h"

static const uint32_t BAUD = 115200;

// ============================================================
// 핀 정의 — UNO R4 WiFi 메인 (릴레이/트랜지스터 경유, GPIO 직결 금지)
// RepRap 패널(2004A 등)은 UNO R3 슬레이브가 I2C로 담당
static const int LED_A1 = 2;
static const int LED_A2 = 3;
static const int PUMP_A1 = 4;
static const int PUMP_A2 = 5;
static const int LED_B1 = 6;
static const int PUMP_B1 = 7;
static const int PUMP_B2 = 8;
static const int PUMP_C1 = 9;
static const int PUMP_C2 = 10;
static const int PUMP_D1 = 11;
static const int PUMP_D2 = 12;

// UART 패널(Mega) 표시 — Tx/Rx 링크 실패 시 false, 로직·MQTT는 계속 동작
static bool gPanelReady = false;
static bool gLcdWelcomed = false;
static uint32_t gLcdWelcomeAtMs = 0;
static uint32_t gLastLcdRtcMs = 0;
// 패널 브라우즈 화면 갱신(엔코더·적용 직후 + 주기적 STATE 반영)
static bool gPanelBrowseDirty = true;
static uint32_t gLastBrowseDrawMs = 0;
// 환영/부팅 상태에서 "푸시=EDIT"로 들어가 버리는 것을 막기 위해,
// 실제로 브라우즈 화면(4줄)이 한 번이라도 그려졌는지 추적합니다.
static bool gPanelBrowseShown = false;
static const uint32_t PANEL_WELCOME_MS = 5000;
static const uint32_t PANEL_BROWSE_REFRESH_MS = 800;
static bool gPanelUiDirty = true;          // EDIT 화면용: dirty일 때만 4줄 강제 갱신
static uint32_t gLastEditDrawMs = 0;
static const uint32_t PANEL_EDIT_REFRESH_MS = 400;
static bool gUiStartFromWelcomePending = false; // 환영 화면에서 입력 시 CH1부터 시작(1회)
static const uint32_t PANEL_UART_BAUD = 19200;
#define CF_PANEL_UART Serial1
static char gPanelRxLine[96];
static uint8_t gPanelRxLen = 0;
static bool gPanelLineInit[4] = { false, false, false, false };
static char gPanelLineCache[4][21];
static uint32_t gPanelLastTxUs = 0;

static void panelUartTxPace() {
  // UART 스트림이 섞여 라인 경계가 흔들리는 문제를 완화하기 위한 전송 간격 제한
  const uint32_t minGapUs = 6000; // 6ms
  const uint32_t nowUs = (uint32_t)micros();
  if (gPanelLastTxUs != 0) {
    const uint32_t gap = nowUs - gPanelLastTxUs;
    if (gap < minGapUs) {
      delayMicroseconds((int)(minGapUs - gap));
    }
  }
  gPanelLastTxUs = (uint32_t)micros();
}

static void panelClear();
static void panelPrintLine(uint8_t row, const char* text);
static void panelBeepShort();
static void panelBeepLong();
static void panelSetBlink(uint8_t row, uint8_t col, bool on);
static void panelPollEvents(uint32_t nowMs);
static void lcdWelcomeIfOk(uint32_t nowMs, bool wifiOk, bool mqttOk);
static void lcdBrowseDraw(uint32_t nowMs);

static void panelSetFansMask(uint8_t fanMask);
static uint8_t gRemoteFanMask = 0;
static void panelSetRemoteGpio(uint8_t idx, bool on);

// ============================================================
// LCD + 엔코더 UI는 채널 정의/배열 이후에 선언(선언 순서 의존성 방지)
enum UiMode : uint8_t { UI_BROWSE = 0, UI_EDIT = 1 };
static UiMode gUiMode = UI_BROWSE;
static uint8_t gUiCh = 0;
static bool gUiPickOn = false;
static bool gUiEditOrigOn = false;

static uint32_t gBtnLastMs = 0;

static void beepShort();
static void beepLong();
static void uiApplySelection(uint8_t ch, bool on);
static void lcdRenderUi(uint32_t nowMs, bool wifiOk, bool mqttOk);
static void encoderDelta(int8_t d);
static void panelHandleClick(uint32_t nowMs);

// 채널 정의(표시/제어용)
enum Channel : uint8_t {
  CH_LED_A1 = 0,
  CH_LED_A2 = 1,
  CH_LED_B1 = 2,
  CH_PUMP_A1 = 3,
  CH_PUMP_A2 = 4,
  CH_PUMP_B1 = 5,
  CH_PUMP_B2 = 6,
  CH_PUMP_C1 = 7,
  CH_PUMP_C2 = 8,
  CH_PUMP_D1 = 9,
  CH_PUMP_D2 = 10,
  CH_FAN_A1 = 11,
  CH_FAN_A2 = 12,
  CH_FAN_B1 = 13,
  CH_FAN_B2 = 14,
  CH_SERVO0 = 15,
  CH_SERVO1 = 16,
  CH_SERVO2 = 17,
  CH_SERVO3 = 18,
  CH_COUNT = 19
};

static inline bool chIsRemote(uint8_t ch) {
  // TriGorilla(Mega) GPIO로 제어되는 채널들(FAN/SERVO)
  return (ch >= CH_FAN_A1 && ch < CH_COUNT);
}

// 다이얼로 UI를 순환할 채널 순서(항상 고정)
// 사용자가 요청한 CH1~CH19 순서 그대로 고정합니다.
static const uint8_t UI_CH_ORDER[CH_COUNT] = {
  CH_LED_A1,   // CH1
  CH_LED_A2,   // CH2
  CH_LED_B1,   // CH3
  CH_PUMP_A1,  // CH4
  CH_PUMP_A2,  // CH5
  CH_PUMP_B1,  // CH6
  CH_PUMP_B2,  // CH7
  CH_PUMP_C1,  // CH8
  CH_PUMP_C2,  // CH9
  CH_PUMP_D1,  // CH10
  CH_PUMP_D2,  // CH11
  CH_FAN_A1,   // CH12
  CH_FAN_A2,   // CH13
  CH_FAN_B1,   // CH14
  CH_FAN_B2,   // CH15
  CH_SERVO0,   // CH16
  CH_SERVO1,   // CH17
  CH_SERVO2,   // CH18
  CH_SERVO3,   // CH19
};

static int8_t uiOrderPos(uint8_t ch) {
  for (uint8_t i = 0; i < CH_COUNT; i++) {
    if (UI_CH_ORDER[i] == ch) return (int8_t)i;
  }
  return -1;
}

static uint8_t uiNextCh(uint8_t cur, int8_t dir) {
  int8_t pos = uiOrderPos(cur);
  if (pos < 0) pos = 0;
  pos += (dir > 0) ? 1 : -1;
  if (pos < 0) pos = (int8_t)CH_COUNT - 1;
  if (pos >= (int8_t)CH_COUNT) pos = 0;
  return UI_CH_ORDER[(uint8_t)pos];
}

static inline bool isInWelcomeWindow() {
  return gLcdWelcomed && (int32_t)(millis() - gLcdWelcomeAtMs) < (int32_t)PANEL_WELCOME_MS;
}

static void forceStartFromCh1();

// 로컬 GPIO 제어 채널만 핀을 가집니다. TriGorilla(FAN/SERVO) 채널은 UART로 전달(원격)이라 -1로 둡니다.
static const int CH_PIN[CH_COUNT] = {
  LED_A1,   // CH_LED_A1
  LED_A2,   // CH_LED_A2
  LED_B1,   // CH_LED_B1
  PUMP_A1,  // CH_PUMP_A1
  PUMP_A2,  // CH_PUMP_A2
  PUMP_B1,  // CH_PUMP_B1
  PUMP_B2,  // CH_PUMP_B2
  PUMP_C1,  // CH_PUMP_C1
  PUMP_C2,  // CH_PUMP_C2
  PUMP_D1,  // CH_PUMP_D1
  PUMP_D2,  // CH_PUMP_D2
  -1,       // CH_FAN_A1 (TG)
  -1,       // CH_FAN_A2 (TG)
  -1,       // CH_FAN_B1 (TG)
  -1,       // CH_FAN_B2 (TG)
  -1,       // CH_SERVO0 (TG)
  -1,       // CH_SERVO1 (TG)
  -1,       // CH_SERVO2 (TG)
  -1,       // CH_SERVO3 (TG)
};

static const char* const CH_KEY[CH_COUNT] = {
  "led_a1",
  "led_a2",
  "led_b1",
  "pump_a1",
  "pump_a2",
  "pump_b1",
  "pump_b2",
  "pump_c1",
  "pump_c2",
  "pump_d1",
  "pump_d2",
  "fan_a1",
  "fan_a2",
  "fan_b1",
  "fan_b2",
  "servo0",
  "servo1",
  "servo2",
  "servo3",
};

static const char* const CH_LABEL_KO[CH_COUNT] = {
  "LED A1",  "LED A2",  "LED B1",
  "PUMP A1", "PUMP A2", "PUMP B1", "PUMP B2",
  "PUMP C1", "PUMP C2", "PUMP D1", "PUMP D2",
  "FAN A1",  "FAN A2",  "FAN B1",  "FAN B2",
  "SERVO0",  "SERVO1",  "SERVO2",  "SERVO3",
};

// 채널별 AUTO(1)/수동(0)
static bool chAuto[CH_COUNT] = {
  false, false, false, // LED A1/A2/B1
  true, true,          // PUMP A1/A2
  true, true,          // PUMP B1/B2
  true, true,          // PUMP C1/C2
  true, true,          // PUMP D1/D2
  false, false, false, false, // FAN A1/A2/B1/B2
  false, false, false, false  // SERVO0~3
};

static const char* chPinLabel(uint8_t ch) {
  switch (ch) {
    case CH_LED_A1: return "D2";
    case CH_LED_A2: return "D3";
    case CH_LED_B1: return "D6";
    case CH_PUMP_A1: return "D4";
    case CH_PUMP_A2: return "D5";
    case CH_PUMP_B1: return "D7";
    case CH_PUMP_B2: return "D8";
    case CH_PUMP_C1: return "D9";
    case CH_PUMP_C2: return "D10";
    case CH_PUMP_D1: return "D11";
    case CH_PUMP_D2: return "D12";
    case CH_FAN_A1: return "TG-D3";
    case CH_FAN_A2: return "TG-D2";
    case CH_FAN_B1: return "TG-D14";
    case CH_FAN_B2: return "TG-D15";
    case CH_SERVO0: return "TG-SERVO0";
    case CH_SERVO1: return "TG-SERVO1";
    case CH_SERVO2: return "TG-SERVO2";
    case CH_SERVO3: return "TG-SERVO3";
    default: return "?";
  }
}

// 채널별 수동 상태·타이머·출력 — lcdBrowseDraw·패널 UI보다 먼저 두어 컴파일 순서 충족
static bool chManual[CH_COUNT] = {
  false, false, false,
  false, false, false, false,
  false, false, false, false,
  false, false, false, false,
  false, false, false, false
};
// MQTT(cmd)와 패널(UI) 동시 제어 시, 패널에서 막 바꾼 상태가 즉시 덮어써져 OFF로 “튀는” 현상 방지용
static uint32_t gUiLocalOverrideAtMs[CH_COUNT] = {
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
};
static const uint32_t UI_LOCAL_OVERRIDE_HOLD_MS = 3000;
static uint32_t chOnMs[CH_COUNT]  = {
  0, 0, 0,                 // LED
  30000, 30000,            // PUMP A
  30000, 30000,            // PUMP B
  30000, 30000,            // PUMP C
  30000, 30000,            // PUMP D
  0, 0, 0, 0,              // FAN
  0, 0, 0, 0               // SERVO
};
static uint32_t chOffMs[CH_COUNT] = {
  0, 0, 0,                 // LED
  90000, 90000,            // PUMP A
  90000, 90000,            // PUMP B
  90000, 90000,            // PUMP C
  90000, 90000,            // PUMP D
  0, 0, 0, 0,              // FAN
  0, 0, 0, 0               // SERVO
};
static uint32_t chPrevMs[CH_COUNT] = {
  0,0,0,
  0,0,0,0,
  0,0,0,0,
  0,0,0,0,
  0,0,0,0
};
static bool chState[CH_COUNT] = {
  false, false, false,
  false, false, false, false,
  false, false, false, false,
  false, false, false, false,
  false, false, false, false
};

static void forceStartFromCh1() {
  // 환영 화면에서 다이얼/푸시 입력이 들어오면, 사용자가 현재 CH를 모르므로
  // 무조건 CH1부터 브라우즈 화면을 시작합니다.
  gUiMode = UI_BROWSE;
  gUiCh = UI_CH_ORDER[0];
  gUiPickOn = chIsRemote(gUiCh) ? chState[gUiCh]
                                : (digitalRead((uint8_t)CH_PIN[gUiCh]) == HIGH);
  gPanelBrowseDirty = true;
  gLastBrowseDrawMs = 0;
  gPanelBrowseShown = false;
  gUiStartFromWelcomePending = true;
}

// ---------- UART 패널(Mega) — 마스터 측 ----------
static void panelClear() {
  if (!gPanelReady) {
    return;
  }
  panelUartTxPace();
  CF_PANEL_UART.println("C");
  for (uint8_t r = 0; r < 4; r++) {
    gPanelLineInit[r] = false;
  }
}

static void panelSetLine20(uint8_t row, const char line20[21]) {
  if (!gPanelReady) {
    return;
  }
  if (row > 3) {
    return;
  }
  panelUartTxPace();
  CF_PANEL_UART.print("L,");
  CF_PANEL_UART.print((unsigned)row);
  CF_PANEL_UART.print(",");
  for (uint8_t i = 0; i < 20 && line20[i] != '\0'; i++) {
    const char c = line20[i];
    if (c == '\r' || c == '\n' || c == ',') {
      continue;
    }
    CF_PANEL_UART.print(c);
  }
  CF_PANEL_UART.println();
  strncpy(gPanelLineCache[row], line20, 20);
  gPanelLineCache[row][20] = '\0';
  gPanelLineInit[row] = true;
}

static void panelPrintLine(uint8_t row, const char* text) {
  char buf[21];
  for (uint8_t i = 0; i < 20; i++) {
    buf[i] = ' ';
  }
  buf[20] = '\0';
  if (text) {
    size_t n = strlen(text);
    if (n > 20) {
      n = 20;
    }
    memcpy(buf, text, n);
  }
  panelSetLine20(row, buf);
}

// panelPrintLine과 동일한 20자 패딩(캐시 비교용)
static void panelPadLine20FromText(char out[21], const char* text) {
  for (uint8_t i = 0; i < 20; i++) {
    out[i] = ' ';
  }
  out[20] = '\0';
  if (text) {
    size_t n = strlen(text);
    if (n > 20) {
      n = 20;
    }
    memcpy(out, text, n);
  }
}

static void panelBeepShort() {
  if (!gPanelReady) {
    return;
  }
  panelUartTxPace();
  CF_PANEL_UART.println("B,0");
}

static void panelBeepLong() {
  if (!gPanelReady) {
    return;
  }
  panelUartTxPace();
  CF_PANEL_UART.println("B,1");
}

static void panelSetFansMask(uint8_t fanMask) {
  if (!gPanelReady) {
    return;
  }
  panelUartTxPace();
  CF_PANEL_UART.print("F,");
  CF_PANEL_UART.println((unsigned)(fanMask & 0x07));
}

static void panelSetRemoteGpio(uint8_t idx, bool on) {
  // TriGorilla(Mega) 측 원격 GPIO 제어
  // 프로토콜(추가): "O,<idx>,<0|1>\n"
  // - idx: 0..7 (CH_FAN_A1부터 순서대로)
  if (!gPanelReady) {
    return;
  }
  if (idx > 7) {
    return;
  }
  panelUartTxPace();
  CF_PANEL_UART.print("O,");
  CF_PANEL_UART.print((unsigned)idx);
  CF_PANEL_UART.print(",");
  CF_PANEL_UART.println(on ? "1" : "0");
}

static void allOff();
static void publishTelemetry();

static void panelPollEvents(uint32_t nowMs) {
  while (CF_PANEL_UART.available() > 0) {
    const char c = (char)CF_PANEL_UART.read();
    if (c == '\r' || c == '\n') {
      if (gPanelRxLen == 0) {
        continue;
      }
      gPanelRxLine[gPanelRxLen] = '\0';
      gPanelRxLen = 0;
      gPanelReady = true;

      int t = -1;
      int p = 0;
      if (sscanf(gPanelRxLine, "v=1;type=evt;t=%d;p=%d", &t, &p) == 2) {
        switch ((uint8_t)t) {
          case PANEL_EVT_ENC_CW:
            // 패널(Mega) 펌웨어가 CW/CCW 이벤트를 스왑해서 보내는 배선/보드 케이스가 있어
            // 여기서는 물리 CW가 "증가"로 동작하도록 해석을 반대로 둡니다.
            encoderDelta(-1);
            break;
          case PANEL_EVT_ENC_CCW:
            encoderDelta(+1);
            break;
          case PANEL_EVT_CLICK:
            panelHandleClick(nowMs);
            break;
          case PANEL_EVT_KILL:
            if (p) {
              allOff();
              publishTelemetry();
            }
            break;
          default:
            break;
        }
      }
      continue;
    }
    if (gPanelRxLen < (uint8_t)(sizeof(gPanelRxLine) - 1)) {
      gPanelRxLine[gPanelRxLen++] = c;
    }
  }
}

static const char* dowShortEn(DayOfWeek d) {
  switch (d) {
    case DayOfWeek::SUNDAY: return "Sun";
    case DayOfWeek::MONDAY: return "Mon";
    case DayOfWeek::TUESDAY: return "Tue";
    case DayOfWeek::WEDNESDAY: return "Wed";
    case DayOfWeek::THURSDAY: return "Thu";
    case DayOfWeek::FRIDAY: return "Fri";
    case DayOfWeek::SATURDAY: return "Sat";
    default: return "???";
  }
}

static void lcdRefreshRtcDateTime() {
  if (!gPanelReady) {
    return;
  }
  RTCTime t;
  if (!RTC.getTime(t)) {
    return;
  }
  char lineDate[21];
  char lineTime[21];
  int y = t.getYear();
  int mo = Month2int(t.getMonth());
  int day = t.getDayOfMonth();
  snprintf(lineDate, sizeof(lineDate), "%04d.%02d.%02d (%s)",
           y, mo, day, dowShortEn(t.getDayOfWeek()));
  int h24 = t.getHour();
  int mi = t.getMinutes();
  int s = t.getSeconds();
  bool pm = (h24 >= 12);
  int h12 = h24 % 12;
  if (h12 == 0) {
    h12 = 12;
  }
  snprintf(lineTime, sizeof(lineTime), "%02d:%02d:%02d %s",
           h12, mi, s, pm ? "PM" : "AM");
  panelPrintLine(2, lineDate);
  panelPrintLine(3, lineTime);
}

static void lcdWelcomeIfOk(uint32_t nowMs, bool wifiOk, bool mqttOk) {
  (void)mqttOk;
  if (!gPanelReady) {
    return;
  }
  if (gLcdWelcomed) {
    return;
  }
  // MQTT 없이도 패널 UI 사용 — 브로커 지연/끊김 시 엔코더·채널 화면이 막히지 않게 함
  if (!wifiOk) {
    return;
  }

  panelClear();
  panelPrintLine(0, "Welcome to");
  panelPrintLine(1, "CronusFarm");
  lcdRefreshRtcDateTime();

  gLcdWelcomed = true;
  gLcdWelcomeAtMs = nowMs;
  gLastLcdRtcMs = nowMs;
  gPanelBrowseDirty = true;
}

// 환영(5초) 이후: 채널 순서 LED A1→…→Pump B2, 엔코더로만 이동
static void lcdBrowseDraw(uint32_t nowMs) {
  if (!gPanelReady || !gLcdWelcomed) {
    return;
  }
  if (gUiMode != UI_BROWSE) {
    return;
  }
  if ((nowMs - gLcdWelcomeAtMs) < PANEL_WELCOME_MS) {
    return;
  }

  const uint8_t ch = gUiCh;
  const bool on =
    chIsRemote(ch) ? chState[ch] : (digitalRead((uint8_t)CH_PIN[ch]) == HIGH);
  const bool isAuto = chAuto[ch];

  char line0[21];
  char line1[21];
  char line2[21];
  char line3[21];
  snprintf(line0, sizeof(line0), "%s (%s)", CH_LABEL_KO[ch], chPinLabel(ch));
  // 4줄 브라우즈(고정 포맷)
  // 1) 장치명 (핀/설명)
  // 2) MODE + 간단 설명(스케쥴/로컬)
  // 3) STATE + CH<현재>/<전체> (스페이스 포함 고정)
  // 4) "DIAL Next PUSH Edit"
  snprintf(line1, sizeof(line1), "MODE:%s", isAuto ? "AUTO" : "MAN ");
  const int8_t pos = uiOrderPos(ch);
  const uint8_t orderCh = (pos < 0) ? (uint8_t)(ch + 1) : (uint8_t)(pos + 1);
  // "STATE:ON (또는 OFF) + 공백 4칸 + CHx/y" 고정 정렬
  // - ON은 2글자라 뒤를 1칸 패딩("ON ")으로 맞춥니다.
  const char* state3 = on ? "ON " : "OFF";
  snprintf(line2, sizeof(line2), "STATE:%s    CH%u/%u",
           state3, (unsigned)orderCh, (unsigned)CH_COUNT);
  snprintf(line3, sizeof(line3), "DIAL Next PUSH Edit");

  char pad0[21], pad1[21], pad2[21], pad3[21];
  panelPadLine20FromText(pad0, line0);
  panelPadLine20FromText(pad1, line1);
  panelPadLine20FromText(pad2, line2);
  panelPadLine20FromText(pad3, line3);

  const bool periodic = (nowMs - gLastBrowseDrawMs) >= PANEL_BROWSE_REFRESH_MS;
  const bool rowDiff =
    !gPanelLineInit[0] || (memcmp(pad0, gPanelLineCache[0], 20) != 0) ||
    !gPanelLineInit[1] || (memcmp(pad1, gPanelLineCache[1], 20) != 0) ||
    !gPanelLineInit[2] || (memcmp(pad2, gPanelLineCache[2], 20) != 0) ||
    !gPanelLineInit[3] || (memcmp(pad3, gPanelLineCache[3], 20) != 0);

  if (!gPanelBrowseDirty && !periodic && !rowDiff) {
    return;
  }

  static uint8_t sPrevBrowseUiCh = 0xFF;
  const bool chChanged = (sPrevBrowseUiCh != ch);
  const bool needFullRedraw = !gPanelBrowseShown || chChanged;

  if (needFullRedraw) {
    panelClear();
    panelSetBlink(0, 0, false); // 브라우즈에서는 반전(커서) 표시를 끕니다.
    panelPrintLine(0, line0);
    panelPrintLine(1, line1);
    panelPrintLine(2, line2);
    panelPrintLine(3, line3);
    sPrevBrowseUiCh = ch;
  } else {
    if (!gPanelLineInit[0] || memcmp(pad0, gPanelLineCache[0], 20) != 0) {
      panelPrintLine(0, line0);
    }
    if (!gPanelLineInit[1] || memcmp(pad1, gPanelLineCache[1], 20) != 0) {
      panelPrintLine(1, line1);
    }
    if (!gPanelLineInit[2] || memcmp(pad2, gPanelLineCache[2], 20) != 0) {
      panelPrintLine(2, line2);
    }
    if (!gPanelLineInit[3] || memcmp(pad3, gPanelLineCache[3], 20) != 0) {
      panelPrintLine(3, line3);
    }
  }

  gPanelBrowseDirty = false;
  gLastBrowseDrawMs = nowMs;
  gPanelBrowseShown = true;
}

// ============================================================
// 패널(R3) UI — 엔코더/클릭은 I2C 이벤트로 수신
static void beepShort() {
  panelBeepShort();
}
static void beepLong() {
  panelBeepLong();
}

static void uiApplySelection(uint8_t ch, bool on) {
  if (ch >= CH_COUNT) {
    return;
  }
  chAuto[ch] = false;
  chManual[ch] = on;
  gUiLocalOverrideAtMs[ch] = millis();
  if (chIsRemote(ch)) {
    // TriGorilla 채널은 원격 GPIO로 전달
    const uint8_t ridx = (uint8_t)(ch - CH_FAN_A1); // 0..7
    panelSetRemoteGpio(ridx, on);
    chState[ch] = on;
  } else {
    digitalWrite(CH_PIN[ch], on ? HIGH : LOW);
    chState[ch] = on;
  }
}

static void lcdRenderUi(uint32_t nowMs, bool wifiOk, bool mqttOk) {
  (void)nowMs;
  if (!gPanelReady) {
    return;
  }

  char line0[21];
  char line1[21];
  char line2[21];
  char line3[21];

  // WiFi+MQTT 연결 전 대기 화면
  if (!gLcdWelcomed) {
    snprintf(line0, sizeof(line0), "%s %s", CH_LABEL_KO[gUiCh], chPinLabel(gUiCh));
    snprintf(line1, sizeof(line1), "%s %s", wifiOk ? "WiFi OK" : "WiFi --",
             mqttOk ? " MQTT OK" : " MQTT --");
    snprintf(line2, sizeof(line2), "Waiting link...");
    snprintf(line3, sizeof(line3), "");
    panelPrintLine(0, line0);
    panelPrintLine(1, line1);
    panelPrintLine(2, line2);
    panelPrintLine(3, line3);
    return;
  }

  // 설정 변경 모드(EDIT)
  if (!gPanelUiDirty && (nowMs - gLastEditDrawMs) < PANEL_EDIT_REFRESH_MS) {
    return;
  }
  gLastEditDrawMs = nowMs;
  // 4줄 EDIT(고정 포맷)
  // 1) "Setting Mode (EDIT)" — (EDIT) 강조(커서 블링크로 유사 반전)
  // 2) 장치명 (핀/설명)
  // 3) SET:ON/OFF — 다이얼로 바꾼 값이면 ON/OFF 쪽 커서 블링크로 강조
  // 4) "Dial:On/Off Push:OK"
  snprintf(line0, sizeof(line0), "Setting Mode (EDIT)");
  snprintf(line1, sizeof(line1), "%s (%s)", CH_LABEL_KO[gUiCh], chPinLabel(gUiCh));
  snprintf(line2, sizeof(line2), "SET:%s", gUiPickOn ? "ON" : "OFF");
  snprintf(line3, sizeof(line3), "Dial:On/Off Push:OK");

  // EDIT는 매 갱신마다 4줄 전체를 강제 재전송(환영 시간/잔상 방지)
  panelClear();
  gPanelUiDirty = false;
  panelPrintLine(0, line0);
  panelPrintLine(1, line1);
  panelPrintLine(2, line2);
  panelPrintLine(3, line3);
  // (EDIT) 글자 반전은 LCD 특성상 직접 구현이 어려워, 커서 블링크로 유사 반전 표시합니다.
  // "Setting Mode (EDIT)" 에서 'E' 위치(col=14)로 고정.
  panelSetBlink(0, 14, true);
  // SET 값이 "진입 시 상태"에서 변경되면 강조(SET:의 값 시작 col=4)
  panelSetBlink(2, 4, (gUiPickOn != gUiEditOrigOn));
}

static void encoderDelta(int8_t d) {
  if (d == 0) {
    return;
  }
  if (gUiMode == UI_BROWSE) {
    uint8_t prevCh = gUiCh;
    // 환영 화면에서 첫 입력은 "CH1부터"로 고정하고, 그 입력은 이동으로 처리하지 않습니다.
    if (isInWelcomeWindow()) {
      gLcdWelcomeAtMs = millis() - PANEL_WELCOME_MS; // 즉시 브라우즈로 전환
      forceStartFromCh1();
      for (uint8_t r = 0; r < 4; r++) gPanelLineInit[r] = false;
      return;
    }
    // 환영에서 막 넘어온 직후에는 이미 CH1을 표시했으므로, 첫 이동은 다음 입력부터 반영합니다.
    if (gUiStartFromWelcomePending) {
      gUiStartFromWelcomePending = false;
      for (uint8_t r = 0; r < 4; r++) gPanelLineInit[r] = false;
      gPanelBrowseDirty = true;
      return;
    }
    // 브라우즈 이동은 encoder 부호 그대로 UI 순서를 진행합니다.
    gUiCh = uiNextCh(gUiCh, d);
    gUiPickOn = chIsRemote(gUiCh) ? chState[gUiCh]
                                : (digitalRead((uint8_t)CH_PIN[gUiCh]) == HIGH);
    // 채널이 바뀌면 항상 다시 그리기(환영 5초 안에서는 lcdBrowseDraw가 스킵되지만,
    // 5초 후 첫 갱신 시 최종 채널이 반영되도록 dirty 유지)
    if (prevCh != gUiCh) {
      gPanelBrowseDirty = true;
    }
    if (prevCh != gUiCh && gLcdWelcomed &&
        (int32_t)(millis() - gLcdWelcomeAtMs) >= (int32_t)PANEL_WELCOME_MS) {
      beepShort();
    }
  } else {
    bool prev = gUiPickOn;
    gUiPickOn = !gUiPickOn;
    if (prev != gUiPickOn) {
      beepShort();
      gPanelUiDirty = true; // EDIT 토글이면 4줄 재전송
    }
  }
}

static void panelHandleClick(uint32_t nowMs) {
  if (nowMs - gBtnLastMs < 220) {
    return;
  }
  gBtnLastMs = nowMs;
  if (gUiMode == UI_BROWSE) {
    // 환영 화면에서의 푸시는 EDIT 진입이 아니라 CH1부터 브라우즈 시작으로 처리
    if (!gPanelBrowseShown || !gLcdWelcomed ||
        (int32_t)(millis() - gLcdWelcomeAtMs) < (int32_t)PANEL_WELCOME_MS) {
      if (gLcdWelcomed) {
        gLcdWelcomeAtMs = millis() - PANEL_WELCOME_MS;
      }
      forceStartFromCh1();
      for (uint8_t r = 0; r < 4; r++) gPanelLineInit[r] = false;
      return;
    }
    gUiMode = UI_EDIT;
    gUiPickOn = chIsRemote(gUiCh) ? chState[gUiCh]
                                  : (digitalRead((uint8_t)CH_PIN[gUiCh]) == HIGH);
    gUiEditOrigOn = gUiPickOn;
    beepShort();
    gPanelUiDirty = true;
  } else {
    uiApplySelection(gUiCh, gUiPickOn);
    beepLong();
    publishTelemetry();
    gUiMode = UI_BROWSE;
    gPanelBrowseDirty = true;
    gPanelUiDirty = false;
    panelSetBlink(0, 0, false);
  }
}

static void panelSetBlink(uint8_t row, uint8_t col, bool on) {
  // Mega LCD에서 커서 블링크를 사용해 "반전" 유사 효과를 냅니다.
  // 프로토콜(추가): "H,<row>,<col>,<0|1>\n"
  if (!gPanelReady) {
    return;
  }
  if (row > 3) row = 3;
  if (col > 19) col = 19;
  panelUartTxPace();
  CF_PANEL_UART.print("H,");
  CF_PANEL_UART.print((unsigned)row);
  CF_PANEL_UART.print(",");
  CF_PANEL_UART.print((unsigned)col);
  CF_PANEL_UART.print(",");
  CF_PANEL_UART.println(on ? "1" : "0");
}

static uint32_t lastTelemetryMs = 0;
static const uint32_t TELEMETRY_INTERVAL_MS = 1000;

static WiFiClient net;
static MqttClient mqtt(net);

static char topicCmd[96];
static char topicTele[96];
static char topicStatus[96];
static char topicPiWifi[96];

// EEPROM: [0..34] 선호 SSID — [0]=매직, [1]=길이, [2..]=SSID
// EEPROM: [35..] 동적 AP(목록 외 SSID+비번) — [35]=0xD0, [36]=ssid_len, [37..68]=ssid, [69]=pass_len, [70..133]=pass
static const uint8_t EEPROM_MAGIC = 0xCF;
static const int EEPROM_ADDR_MAGIC = 0;
static const int EEPROM_ADDR_LEN = 1;
static const int EEPROM_ADDR_SSID = 2;
static const uint8_t EEPROM_MAX_SSID_LEN = 32;

static const uint8_t EEPROM_DYN_MAGIC = 0xD0;
static const int EEPROM_ADDR_DYN_MAGIC = 35;
static const int EEPROM_ADDR_DYN_SSID_LEN = 36;
static const int EEPROM_ADDR_DYN_SSID = 37;
static const int EEPROM_ADDR_DYN_PASS_LEN = 69;
static const int EEPROM_ADDR_DYN_PASS = 70;
static const uint8_t EEPROM_MAX_PASS_LEN = 64;

// 내장 12x8 LED 매트릭스 — WiFi/MQTT 상태 표시
static ArduinoLEDMatrix gMatrix;
static uint8_t gMatFrame[8][12];

static void matClear() {
  for (int r = 0; r < 8; r++) {
    for (int c = 0; c < 12; c++) {
      gMatFrame[r][c] = 0;
    }
  }
}

static void matPixel(int r, int c, uint8_t on) {
  if (r < 0 || r >= 8 || c < 0 || c >= 12) return;
  gMatFrame[r][c] = on ? 1 : 0;
}

// 매트릭스 표시 방향 보정
// - 논리 좌표(8×12, x=0..7 / y=0..11)를 물리 매트릭스(8×12, r/c)에 매핑합니다.
// - 요청: 안테나/M 글자를 180도 회전해 보이게(=현재 180도 보정 상태에서 한 번 더 180도 회전)
//   → 결과적으로 정방향(보정 없음)으로 표시합니다.
static void matPixelRotNone(int x, int y, uint8_t on) {
  if (x < 0 || x >= 8 || y < 0 || y >= 12) return;
  matPixel(x, y, on);
}

// 8×6 글자(위/아래 2등분 표시용)
// - 위 6줄: WiFi 연결이면 "안테나" 아이콘
// - 아래 6줄: MQTT 연결이면 'M'
static const char GLYPH_W_8x6[6][9] = {
  "O.......",
  "O.O.....",
  "O.O.O...",
  "O.O.O.O.",
  "O.O.O.OO",
  "........",
};

static const char GLYPH_M_8x6[6][9] = {
  "OO...OO.",
  "OOO.OOO.",
  "O.O.O.O.",
  "O..O..O.",
  "O.....O.",
  "O.....O.",
};

static void matBlitGlyph8x6(int y0, const char glyph[6][9]) {
  for (int r = 0; r < 6; r++) {
    for (int c = 0; c < 8; c++) {
      const char ch = glyph[r][c];
      matPixelRotNone(c, y0 + r, (ch == 'O' || ch == 'o') ? 1u : 0u);
    }
  }
}

static void matRenderStatus(bool wifiOk, bool mqttOk) {
  matClear();
  if (wifiOk) {
    matBlitGlyph8x6(0, GLYPH_W_8x6);
  }
  if (mqttOk) {
    matBlitGlyph8x6(6, GLYPH_M_8x6);
  }
  gMatrix.renderBitmap(gMatFrame, 8, 12);
}

static void matrixTick(uint32_t nowMs, bool wifiOk, bool mqttOk) {
  static bool prevW = false;
  static bool prevM = false;
  static bool first = true;

  (void)nowMs;
  const bool logicDiff = first || (wifiOk != prevW) || (mqttOk != prevM);

  if (!logicDiff) {
    return;
  }

  first = false;
  prevW = wifiOk;
  prevM = mqttOk;

  matRenderStatus(wifiOk, mqttOk);
}

// WiFi/MQTT 상태로 매트릭스 즉시 갱신(setup·연결 직후 등)
static void matrixShowFromPins() {
  matRenderStatus(WiFi.status() == WL_CONNECTED, mqtt.connected());
}

static void allOff() {
  for (uint8_t i = 0; i < CH_COUNT; i++) {
    if (chIsRemote(i)) {
      const uint8_t ridx = (uint8_t)(i - CH_FAN_A1);
      panelSetRemoteGpio(ridx, false);
      chState[i] = false;
    } else {
      digitalWrite(CH_PIN[i], LOW);
      chState[i] = false;
    }
  }
  gRemoteFanMask = 0;
  panelSetFansMask(gRemoteFanMask);
}

static void publishTelemetry() {
  if (!mqtt.connected()) return;
  // S/A/T + WiFi(ssid 최대 길이) 여유
  char payload[384];

  // tele: 채널 상태 + 채널별 AUTO + (펌프류) on/off
  // 예) S:led_a1=0 ... | A:led_a1=0 ... | T:pump_a1=30/90 ...
  size_t off = 0;
  off += snprintf(payload + off, sizeof(payload) - off, "S:");
  for (uint8_t i = 0; i < CH_COUNT; i++) {
    int v = 0;
    if (chIsRemote(i)) {
      v = chState[i] ? 1 : 0;
    } else {
      v = (digitalRead(CH_PIN[i]) == HIGH) ? 1 : 0;
    }
    off += snprintf(payload + off, sizeof(payload) - off, "%s=%d%s", CH_KEY[i], v, (i + 1 < CH_COUNT) ? " " : "");
    if (off >= sizeof(payload)) break;
  }
  off += snprintf(payload + off, sizeof(payload) - off, " | A:");
  for (uint8_t i = 0; i < CH_COUNT; i++) {
    off += snprintf(payload + off, sizeof(payload) - off, "%s=%d%s", CH_KEY[i], chAuto[i] ? 1 : 0, (i + 1 < CH_COUNT) ? " " : "");
    if (off >= sizeof(payload)) break;
  }
  off += snprintf(payload + off, sizeof(payload) - off, " | T:");
  bool firstT = true;
  for (uint8_t i = 0; i < CH_COUNT; i++) {
    const bool isPump =
      (i == CH_PUMP_A1 || i == CH_PUMP_A2 ||
       i == CH_PUMP_B1 || i == CH_PUMP_B2 ||
       i == CH_PUMP_C1 || i == CH_PUMP_C2 ||
       i == CH_PUMP_D1 || i == CH_PUMP_D2);
    const bool isFan = (i == CH_FAN_A1 || i == CH_FAN_A2 || i == CH_FAN_B1 || i == CH_FAN_B2);
    if (!isPump) continue;
    long onSec = (long)(chOnMs[i] / 1000);
    long offSec = (long)(chOffMs[i] / 1000);
    off += snprintf(payload + off, sizeof(payload) - off, "%s%s=%ld/%ld", firstT ? "" : " ", CH_KEY[i], onSec, offSec);
    firstT = false;
    if (off >= sizeof(payload)) break;
  }
  // tele에 아두이노 WiFi SSID·IP 포함(Node-RED tele raw / 구독자 확인용). WL_CONNECTED일 때만 유효.
  if (off < sizeof(payload)) {
    off += snprintf(payload + off, sizeof(payload) - off, " | W:");
    if (WiFi.status() == WL_CONNECTED) {
      String ss = WiFi.SSID();
      IPAddress lip = WiFi.localIP();
      off += snprintf(payload + off, sizeof(payload) - off, "ssid=%s ip=%u.%u.%u.%u", ss.c_str(),
                      (unsigned)lip[0], (unsigned)lip[1], (unsigned)lip[2], (unsigned)lip[3]);
    } else {
      off += snprintf(payload + off, sizeof(payload) - off, "ssid= ip=0.0.0.0");
    }
  }
  mqtt.beginMessage(topicTele);
  mqtt.print(payload);
  mqtt.endMessage();

  Serial.println(payload);
}

static void buildTopics() {
  snprintf(topicCmd, sizeof(topicCmd), "cronusfarm/%s/cmd", DEVICE_ID);
  snprintf(topicTele, sizeof(topicTele), "cronusfarm/%s/tele", DEVICE_ID);
  snprintf(topicStatus, sizeof(topicStatus), "cronusfarm/%s/status", DEVICE_ID);
  snprintf(topicPiWifi, sizeof(topicPiWifi), "%s", MQTT_TOPIC_PI_WIFI_SSID);
}

static const char* findPassForSsid(const char* ssid) {
  if (!ssid || !*ssid) return nullptr;
  for (int i = 0; i < WIFI_AP_COUNT; i++) {
    if (strcmp(ssid, WIFI_AP_SSIDS[i]) == 0) return WIFI_AP_PASSES[i];
  }
  if (EEPROM.read(EEPROM_ADDR_DYN_MAGIC) != EEPROM_DYN_MAGIC) return nullptr;
  uint8_t sl = EEPROM.read(EEPROM_ADDR_DYN_SSID_LEN);
  if (sl == 0 || sl > EEPROM_MAX_SSID_LEN) return nullptr;
  char buf[33];
  for (uint8_t i = 0; i < sl; i++) {
    buf[i] = (char)EEPROM.read(EEPROM_ADDR_DYN_SSID + (int)i);
  }
  buf[sl] = '\0';
  if (strcmp(ssid, buf) != 0) return nullptr;
  uint8_t pl = EEPROM.read(EEPROM_ADDR_DYN_PASS_LEN);
  if (pl == 0 || pl > EEPROM_MAX_PASS_LEN) return nullptr;
  static char dynPassBuf[65];
  for (uint8_t i = 0; i < pl; i++) {
    dynPassBuf[i] = (char)EEPROM.read(EEPROM_ADDR_DYN_PASS + (int)i);
  }
  dynPassBuf[pl] = '\0';
  return dynPassBuf;
}

static void saveDynamicCredential(const char* ssid, const char* pass) {
  if (!ssid || !pass) return;
  size_t sl = strlen(ssid);
  size_t pl = strlen(pass);
  if (sl > EEPROM_MAX_SSID_LEN) sl = EEPROM_MAX_SSID_LEN;
  if (pl > EEPROM_MAX_PASS_LEN) pl = EEPROM_MAX_PASS_LEN;
  EEPROM.write(EEPROM_ADDR_DYN_MAGIC, EEPROM_DYN_MAGIC);
  EEPROM.write(EEPROM_ADDR_DYN_SSID_LEN, (uint8_t)sl);
  for (size_t i = 0; i < sl; i++) {
    EEPROM.write(EEPROM_ADDR_DYN_SSID + (int)i, ssid[i]);
  }
  for (size_t i = sl; i < EEPROM_MAX_SSID_LEN; i++) {
    EEPROM.write(EEPROM_ADDR_DYN_SSID + (int)i, 0);
  }
  EEPROM.write(EEPROM_ADDR_DYN_PASS_LEN, (uint8_t)pl);
  for (size_t i = 0; i < pl; i++) {
    EEPROM.write(EEPROM_ADDR_DYN_PASS + (int)i, pass[i]);
  }
  for (size_t i = pl; i < EEPROM_MAX_PASS_LEN; i++) {
    EEPROM.write(EEPROM_ADDR_DYN_PASS + (int)i, 0);
  }
}

static void trimPayload(char* s) {
  if (!s) return;
  while (*s == ' ' || *s == '\t') s++;
  size_t len = strlen(s);
  while (len > 0 && (s[len - 1] == '\r' || s[len - 1] == '\n' || s[len - 1] == ' ' || s[len - 1] == '\t')) {
    s[--len] = '\0';
  }
}

static void loadPreferredSsid(char* out, size_t outSz) {
  out[0] = '\0';
  if (outSz < 2) return;
  if (EEPROM.read(EEPROM_ADDR_MAGIC) != EEPROM_MAGIC) return;
  uint8_t len = EEPROM.read(EEPROM_ADDR_LEN);
  if (len == 0 || len >= outSz || len > EEPROM_MAX_SSID_LEN) return;
  for (uint8_t i = 0; i < len; i++) {
    out[i] = (char)EEPROM.read(EEPROM_ADDR_SSID + (int)i);
  }
  out[len] = '\0';
}

static void savePreferredSsid(const char* ssid) {
  if (!ssid) return;
  size_t len = strlen(ssid);
  if (len > EEPROM_MAX_SSID_LEN) len = EEPROM_MAX_SSID_LEN;
  EEPROM.write(EEPROM_ADDR_MAGIC, EEPROM_MAGIC);
  EEPROM.write(EEPROM_ADDR_LEN, (uint8_t)len);
  for (size_t i = 0; i < len; i++) {
    EEPROM.write(EEPROM_ADDR_SSID + (int)i, ssid[i]);
  }
}

static bool tryConnectSsid(const char* ssid, const char* pass, uint32_t timeoutMs) {
  if (!ssid || !pass) return false;
  WiFi.disconnect();
  delay(200);
  WiFi.begin(ssid, pass);
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - t0) < timeoutMs) {
    delay(300);
  }
  return WiFi.status() == WL_CONNECTED;
}

static bool connectByScanBestRssi() {
  Serial.println(F("WiFi 스캔(목록 중 RSSI 최대)..."));
  WiFi.disconnect();
  delay(100);
  int n = WiFi.scanNetworks();
  if (n <= 0) {
    Serial.println(F("스캔 결과 없음"));
    return false;
  }
  int bestIdx = -1;
  int bestRssi = -9999;
  for (int i = 0; i < n; i++) {
    String s = WiFi.SSID(i);
    if (s.length() == 0) continue;
    const char* pw = findPassForSsid(s.c_str());
    if (!pw) continue;
    int rssi = WiFi.RSSI(i);
    if (rssi > bestRssi) {
      bestRssi = rssi;
      bestIdx = i;
    }
  }
  if (bestIdx < 0) {
    Serial.println(F("목록과 일치하는 SSID 없음"));
    return false;
  }
  String pick = WiFi.SSID(bestIdx);
  Serial.print(F("선택 SSID: "));
  Serial.print(pick);
  Serial.print(F(" RSSI: "));
  Serial.println(WiFi.RSSI(bestIdx));
  const char* pw = findPassForSsid(pick.c_str());
  return tryConnectSsid(pick.c_str(), pw, 20000);
}

static bool connectByTryingAllAps() {
  Serial.println(F("후보 AP 순차 시도..."));
  for (int i = 0; i < WIFI_AP_COUNT; i++) {
    Serial.print(F("시도: "));
    Serial.println(WIFI_AP_SSIDS[i]);
    if (tryConnectSsid(WIFI_AP_SSIDS[i], WIFI_AP_PASSES[i], 12000)) return true;
  }
  return false;
}

static void handlePiWifiSsid(char* payload) {
  trimPayload(payload);
  if (!*payload) return;

  char* sp = strchr(payload, ' ');
  if (sp) {
    *sp = '\0';
    sp++;
    while (*sp == ' ' || *sp == '\t') sp++;
    if (*sp) {
      const char* newSsid = payload;
      const char* newPass = sp;
      saveDynamicCredential(newSsid, newPass);
      savePreferredSsid(newSsid);
      Serial.print(F("Pi SSID+비번 EEPROM 저장, 재연결: "));
      Serial.println(newSsid);
      if (!tryConnectSsid(newSsid, newPass, 20000)) {
        Serial.println(F("WiFi 재연결 실패"));
      } else {
        Serial.print(F("WiFi 재연결됨, IP: "));
        Serial.println(WiFi.localIP());
      }
      mqtt.stop();
      return;
    }
  }

  const char* pw = findPassForSsid(payload);
  if (!pw) {
    Serial.print(F("목록/저장에 없는 SSID: "));
    Serial.print(payload);
    Serial.println(F(" — Pi에서 'SSID 비밀번호' 한 번 발행 필요"));
    return;
  }
  Serial.print(F("Pi SSID 수신, EEPROM 저장 후 재연결: "));
  Serial.println(payload);
  savePreferredSsid(payload);
  if (!tryConnectSsid(payload, pw, 20000)) {
    Serial.println(F("WiFi 재연결 실패"));
  } else {
    Serial.print(F("WiFi 재연결됨, IP: "));
    Serial.println(WiFi.localIP());
  }
  mqtt.stop();
}

static void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  char pref[36];
  loadPreferredSsid(pref, sizeof(pref));

  if (pref[0] != '\0') {
    const char* pw = findPassForSsid(pref);
    if (pw) {
      Serial.print(F("WiFi 선호(EEPROM): "));
      Serial.println(pref);
      if (tryConnectSsid(pref, pw, 18000)) {
        Serial.print(F("WiFi 연결됨, IP: "));
        Serial.println(WiFi.localIP());
        return;
      }
      Serial.println(F("선호 AP 실패, 목록 순서/스캔으로 재시도"));
    }
  }

  // secrets.h 의 WIFI_AP_SSIDS 순서대로 먼저 시도(ida와 동일 AP를 배열 **앞쪽**에 두면 우선 연결)
  if (connectByTryingAllAps()) {
    Serial.print(F("WiFi 연결됨, IP: "));
    Serial.println(WiFi.localIP());
    return;
  }

  if (connectByScanBestRssi()) {
    Serial.print(F("WiFi 연결됨, IP: "));
    Serial.println(WiFi.localIP());
    return;
  }

  Serial.println(F("WiFi 연결 실패"));
  delay(2000);
}

static void connectMqtt() {
  if (mqtt.connected()) return;

  // ArduinoMqttClient 기본 TX 버퍼는 보드별로 작음(예: 256B). tele에 S|A|T|W를 붙이면
  // 크기 초과 시 끝(| W:ssid=... ip=...)이 잘려 Node-RED tele raw에 안 보임.
  mqtt.setTxPayloadSize(512);

  mqtt.setId(DEVICE_ID);
  if (strlen(MQTT_USER) > 0) {
    mqtt.setUsernamePassword(MQTT_USER, MQTT_PASS);
  }

  Serial.print("MQTT 연결: ");
  Serial.print(MQTT_HOST);
  Serial.print(":");
  Serial.println(MQTT_PORT);

  // 무한 재시도하면 setup/loop가 막혀 매트릭스가 갱신되지 않음 → loop에서 재시도
  if (!mqtt.connect(MQTT_HOST, MQTT_PORT)) {
    Serial.print(F("MQTT 연결 실패: "));
    Serial.println(mqtt.connectError());
    return;
  }

  mqtt.subscribe(topicCmd, 1);
  mqtt.subscribe(topicPiWifi, 1);
  mqtt.beginMessage(topicStatus, true, 1);
  mqtt.print("online");
  mqtt.endMessage();

  Serial.println("MQTT 연결됨/구독 완료");
}

static void applySingleCharCmd(const char cmd, const char* rest) {
  // 기존 Serial 호환 명령은 더 이상 사용하지 않습니다.
  // (다채널/채널별 AUTO/주기 구조로 전환)
  (void)cmd;
  (void)rest;
}

static void applyKeyValue(const char* key, const char* value) {
  if (!key || !*key || !value || !*value) return;

  auto parseBool = [](const char* v) -> bool {
    return (strcmp(v, "1") == 0 || strcasecmp(v, "on") == 0 || strcasecmp(v, "true") == 0);
  };

  // 1) 채널 수동 상태: led_a1=0/1 ...
  for (uint8_t i = 0; i < CH_COUNT; i++) {
    if (strcmp(key, CH_KEY[i]) == 0) {
      // 패널에서 막 바꾼 값은 잠깐 MQTT로 덮어쓰지 않게 합니다.
      const uint32_t now = millis();
      if (gUiLocalOverrideAtMs[i] != 0 &&
          (int32_t)(now - gUiLocalOverrideAtMs[i]) < (int32_t)UI_LOCAL_OVERRIDE_HOLD_MS) {
        return;
      }
      chManual[i] = parseBool(value);
      return;
    }
  }

  // 2) 채널별 AUTO: auto_led_a1=0/1 ...
  if (strncmp(key, "auto_", 5) == 0) {
    const char* sub = key + 5;
    for (uint8_t i = 0; i < CH_COUNT; i++) {
      if (strcmp(sub, CH_KEY[i]) == 0) {
        chAuto[i] = parseBool(value);
        return;
      }
    }
    return;
  }

  // 3) 채널별 주기(초): on_pump_a1=30, off_pump_a1=90 ...
  if (strncmp(key, "on_", 3) == 0 || strncmp(key, "off_", 4) == 0) {
    const bool isOn = (key[0] == 'o' && key[1] == 'n' && key[2] == '_');
    const char* sub = isOn ? (key + 3) : (key + 4);
    long v = strtol(value, nullptr, 10);
    if (v < 1) v = 1;
    for (uint8_t i = 0; i < CH_COUNT; i++) {
      if (strcmp(sub, CH_KEY[i]) == 0) {
        if (isOn) chOnMs[i] = (uint32_t)v * 1000u;
        else chOffMs[i] = (uint32_t)v * 1000u;
        return;
      }
    }
    return;
  }
}

static void handleCmdPayload(char* buf) {
  // 1) 단일 문자 명령(원본 Serial 코드 호환)
  // 2) key=value 토큰(공백 구분)
  if (!buf || !*buf) return;

  // 앞 공백 제거
  while (*buf == ' ' || *buf == '\t' || *buf == '\r' || *buf == '\n') buf++;
  if (!*buf) return;

  // 단일 문자 모드: 첫 글자가 [A-Za-z] 이고, 이후에 '='가 없으면 단일 명령으로 처리
  if (((buf[0] >= 'A' && buf[0] <= 'Z') || (buf[0] >= 'a' && buf[0] <= 'z')) && strchr(buf, '=') == nullptr) {
    applySingleCharCmd(buf[0], buf + 1);
    return;
  }

  // key=value 토큰 파싱
  char* p = buf;
  while (*p) {
    while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') p++;
    if (!*p) break;

    char* token = p;
    while (*p && *p != ' ' && *p != '\t' && *p != '\r' && *p != '\n') p++;
    if (*p) { *p = '\0'; p++; }

    char* eq = strchr(token, '=');
    if (!eq) continue;
    *eq = '\0';
    const char* key = token;
    const char* value = eq + 1;
    applyKeyValue(key, value);
  }
}

static void pollMqtt() {
  int msgSize = mqtt.parseMessage();
  if (msgSize <= 0) return;

  String t = mqtt.messageTopic();

  char payload[160];
  int i = 0;
  while (mqtt.available() && i < (int)sizeof(payload) - 1) {
    payload[i++] = (char)mqtt.read();
  }
  payload[i] = '\0';

  if (t == String(topicCmd)) {
    Serial.print(F("CMD 수신: "));
    Serial.println(payload);
    handleCmdPayload(payload);
    return;
  }
  if (t == String(topicPiWifi)) {
    Serial.print(F("Pi WiFi 토픽 수신: "));
    Serial.println(payload);
    handlePiWifiSsid(payload);
    return;
  }
}

void setup() {
  for (uint8_t i = 0; i < CH_COUNT; i++) {
    const int p = CH_PIN[i];
    if (p >= 0) {
      pinMode((uint8_t)p, OUTPUT);
    }
  }
  allOff();

  Serial.begin(BAUD);
  delay(200);

  CF_PANEL_UART.begin(PANEL_UART_BAUD);
  delay(2);
  gPanelReady = true;
  panelPrintLine(0, "CronusFarm");
  panelPrintLine(1, "부팅중...");

  gMatrix.begin();
  // begin 직후 한 번 그리기(MQTT 대기로 setup이 안 끝나도 이후 WiFi 성공 시 다시 갱신)
  matRenderStatus(false, false);

  gUiCh = 0;
  gUiPickOn = false;

  RTC.begin();
  // RTC 시각은 코인셀/백업 또는 별도 설정으로 맞춰야 합니다(여기서 임의 setTime 하지 않음).

  buildTopics();
  connectWiFi();
  matrixShowFromPins();
  connectMqtt();
  matrixShowFromPins();
  publishTelemetry();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }
  if (!mqtt.connected()) {
    connectMqtt();
  }

  pollMqtt();

  uint32_t now = millis();
  // UART 이벤트가 들어오면 panelPollEvents에서 gPanelReady=true로 유지됩니다.
  // 링크 순간 끊김이 있어도 화면/로직이 멈추지 않도록 여기서는 강제로 false로 내리지 않습니다.
  panelPollEvents(now);

  // 채널별 AUTO/수동 처리
  // - AUTO=1: 해당 채널이 펌프류면 on/off 주기로 토글, LED류면 수동(기본 OFF) 유지
  // - AUTO=0: chManual[] 값대로 출력
  for (uint8_t i = 0; i < CH_COUNT; i++) {
    const bool isPump =
      (i == CH_PUMP_A1 || i == CH_PUMP_A2 ||
       i == CH_PUMP_B1 || i == CH_PUMP_B2 ||
       i == CH_PUMP_C1 || i == CH_PUMP_C2 ||
       i == CH_PUMP_D1 || i == CH_PUMP_D2);
    const bool isFan = (i == CH_FAN_A1 || i == CH_FAN_A2 || i == CH_FAN_B1 || i == CH_FAN_B2);

    if (!chAuto[i]) {
      if (chIsRemote(i)) {
        const bool on = chManual[i];
        const uint8_t ridx = (uint8_t)(i - CH_FAN_A1);
        panelSetRemoteGpio(ridx, on);
        chState[i] = on;
      } else {
        digitalWrite(CH_PIN[i], chManual[i] ? HIGH : LOW);
        chState[i] = chManual[i];
      }
      continue;
    }

    if (!isPump && !isFan) {
      if (!chIsRemote(i)) {
        digitalWrite(CH_PIN[i], LOW);
      }
      chState[i] = false;
      continue;
    }

    // FAN은 AUTO를 아직 사용하지 않습니다(예상치 못한 분사/환기 방지)
    if (isFan) {
      if (chIsRemote(i)) {
        const uint8_t ridx = (uint8_t)(i - CH_FAN_A1);
        panelSetRemoteGpio(ridx, false);
      }
      chState[i] = false;
      continue;
    }

    uint32_t nowMs = millis();
    uint32_t interval = chState[i] ? chOnMs[i] : chOffMs[i];
    if (interval < 200) interval = 200;
    if (nowMs - chPrevMs[i] >= interval) {
      chPrevMs[i] = nowMs;
      chState[i] = !chState[i];
      if (!chIsRemote(i)) {
        digitalWrite(CH_PIN[i], chState[i] ? HIGH : LOW);
      }
    }
  }

  if (now - lastTelemetryMs >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryMs = now;
    publishTelemetry();
  }

  bool wifiOk = (WiFi.status() == WL_CONNECTED);
  bool mqttOk = mqtt.connected();
  matrixTick(now, wifiOk, mqttOk);

  // 패널: WiFi+MQTT 후 환영(5초)→채널 브라우즈 / 다이얼=채널·편집·비프
  lcdWelcomeIfOk(now, wifiOk, mqttOk);
  if (gLcdWelcomed && gUiMode == UI_BROWSE &&
      (now - gLcdWelcomeAtMs) < PANEL_WELCOME_MS) {
    if (now - gLastLcdRtcMs >= 1000) {
      gLastLcdRtcMs = now;
      lcdRefreshRtcDateTime();
    }
  }
  if (gUiMode == UI_EDIT) {
    lcdRenderUi(now, wifiOk, mqttOk);
  } else if (!gLcdWelcomed) {
    lcdRenderUi(now, wifiOk, mqttOk);
  } else {
    lcdBrowseDraw(now);
  }
}

