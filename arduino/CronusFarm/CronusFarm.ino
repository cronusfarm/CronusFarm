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
#include <Wire.h>

#include "panel_i2c_protocol.h"
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

// I2C 패널(R3) 표시 — Wire 실패 시 false, 로직·MQTT는 계속 동작
static bool gPanelReady = false;
static bool gLcdWelcomed = false;
static uint32_t gLcdWelcomeAtMs = 0;
static uint32_t gLastLcdRtcMs = 0;
// 패널 브라우즈 화면 갱신(엔코더·적용 직후 + 주기적 STATE 반영)
static bool gPanelBrowseDirty = true;
static uint32_t gLastBrowseDrawMs = 0;
static const uint32_t PANEL_WELCOME_MS = 5000;
static const uint32_t PANEL_BROWSE_REFRESH_MS = 400;
static uint32_t gNextPanelProbeMs = 0;

static bool panelProbe();
static void panelClear();
static void panelPrintLine(uint8_t row, const char* text);
static void panelBeepShort();
static void panelBeepLong();
static void panelPollEvents(uint32_t nowMs);
static void lcdWelcomeIfOk(uint32_t nowMs, bool wifiOk, bool mqttOk);
static void lcdBrowseDraw(uint32_t nowMs);

static void panelSetFansMask(uint8_t fanMask);
static uint8_t gRemoteFanMask = 0;

// ============================================================
// LCD + 엔코더 UI는 채널 정의/배열 이후에 선언(선언 순서 의존성 방지)
enum UiMode : uint8_t { UI_BROWSE = 0, UI_EDIT = 1 };
static UiMode gUiMode = UI_BROWSE;
static uint8_t gUiCh = 0;
static bool gUiPickOn = false;

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
  CH_PUMP_A1 = 2,
  CH_PUMP_A2 = 3,
  CH_LED_B1 = 4,
  CH_PUMP_B1 = 5,
  CH_PUMP_B2 = 6,
  CH_FAN_A1 = 7,
  CH_FAN_B1 = 8,
  CH_FAN_B2 = 9,
  CH_COUNT = 10
};

static inline bool chIsRemote(uint8_t ch) {
  return (ch == CH_FAN_A1 || ch == CH_FAN_B1 || ch == CH_FAN_B2);
}

// 로컬 GPIO 제어 채널만 핀을 가집니다. FAN 채널은 Trigorilla로 I2C 전달(원격)이라 -1로 둡니다.
static const int CH_PIN[CH_COUNT] = {
  LED_A1, LED_A2, PUMP_A1, PUMP_A2, LED_B1, PUMP_B1, PUMP_B2,
  -1, -1, -1
};

static const char* const CH_KEY[CH_COUNT] = {
  "led_a1", "led_a2", "pump_a1", "pump_a2", "led_b1", "pump_b1", "pump_b2",
  "fan_a1", "fan_b1", "fan_b2"
};

static const char* const CH_LABEL_KO[CH_COUNT] = {
  "LED A1", "LED A2", "PUMP C1", "PUMP C2", "LED B1", "PUMP D1", "PUMP D2",
  "FAN A1", "FAN B1", "FAN B2"
};

// 채널별 AUTO(1)/수동(0)
static bool chAuto[CH_COUNT] = {
  false, false, true, true, false, true, true,
  false, false, false
};

static const char* chPinLabel(uint8_t ch) {
  switch (ch) {
    case CH_LED_A1: return "D2";
    case CH_LED_A2: return "D3";
    case CH_PUMP_A1: return "D4";
    case CH_PUMP_A2: return "D5";
    case CH_LED_B1: return "D6";
    case CH_PUMP_B1: return "D7";
    case CH_PUMP_B2: return "D8";
    case CH_FAN_A1: return "I2C";
    case CH_FAN_B1: return "I2C";
    case CH_FAN_B2: return "I2C";
    default: return "?";
  }
}

// ---------- I2C 패널(R3) — 마스터 측 ----------
static bool panelProbe() {
  Wire.beginTransmission(PANEL_I2C_ADDR);
  return Wire.endTransmission() == 0;
}

static void panelClear() {
  if (!gPanelReady) {
    return;
  }
  Wire.beginTransmission(PANEL_I2C_ADDR);
  Wire.write(PANEL_CMD_CLEAR);
  if (Wire.endTransmission() != 0) {
    gPanelReady = false;
  }
}

static void panelSetLine20(uint8_t row, const char line20[21]) {
  if (!gPanelReady) {
    return;
  }
  Wire.beginTransmission(PANEL_I2C_ADDR);
  Wire.write(PANEL_CMD_SET_LINE);
  Wire.write(row);
  Wire.write((uint8_t)20);
  for (uint8_t i = 0; i < 20; i++) {
    Wire.write((uint8_t)line20[i]);
  }
  if (Wire.endTransmission() != 0) {
    gPanelReady = false;
  }
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

static void panelBeepShort() {
  if (!gPanelReady) {
    return;
  }
  Wire.beginTransmission(PANEL_I2C_ADDR);
  Wire.write(PANEL_CMD_BEEP);
  Wire.write((uint8_t)0);
  if (Wire.endTransmission() != 0) {
    gPanelReady = false;
  }
}

static void panelBeepLong() {
  if (!gPanelReady) {
    return;
  }
  Wire.beginTransmission(PANEL_I2C_ADDR);
  Wire.write(PANEL_CMD_BEEP);
  Wire.write((uint8_t)1);
  if (Wire.endTransmission() != 0) {
    gPanelReady = false;
  }
}

static void panelSetFansMask(uint8_t fanMask) {
  if (!gPanelReady) {
    return;
  }
  Wire.beginTransmission(PANEL_I2C_ADDR);
  Wire.write(PANEL_CMD_SET_FANS);
  Wire.write((uint8_t)(fanMask & 0x07));
  if (Wire.endTransmission() != 0) {
    gPanelReady = false;
  }
}

static void allOff();
static void publishTelemetry();

static void panelPollEvents(uint32_t nowMs) {
  // gPanelReady=false여도 I2C 이벤트(엔코더/클릭)는 계속 읽어야 합니다.
  // 여기서 return 하면 한번 끊긴 뒤 다이얼이 영구 무반응이 됩니다.
  static uint32_t nextPollMs = 0;
  if ((int32_t)(nowMs - nextPollMs) < 0) {
    return;
  }
  nextPollMs = nowMs + 50;

  static uint8_t fail = 0;
  static uint32_t pollN = 0;
  static uint32_t okN = 0;
  static uint32_t lastLogMs = 0;

  pollN++;
  uint8_t n = Wire.requestFrom((int)PANEL_I2C_ADDR, (int)16);
  if (n < 1) {
    if (++fail >= 20) {
      gPanelReady = false;
      fail = 0;
    }
    // 진단 로그(2초마다): requestFrom 자체가 0바이트인지 확인
    if (nowMs - lastLogMs >= 2000) {
      lastLogMs = nowMs;
      Serial.print(F("[I2C] req poll="));
      Serial.print(pollN);
      Serial.print(F(" ok="));
      Serial.print(okN);
      Serial.print(F(" n="));
      Serial.println(n);
    }
    return;
  }
  fail = 0;
  gPanelReady = true;
  okN++;

  if (nowMs - lastLogMs >= 2000) {
    lastLogMs = nowMs;
    Serial.print(F("[I2C] req poll="));
    Serial.print(pollN);
    Serial.print(F(" ok="));
    Serial.print(okN);
    Serial.print(F(" n="));
    Serial.println(n);
  }

  uint8_t cnt = (uint8_t)Wire.read();
  for (uint8_t i = 0; i < cnt; i++) {
    if (Wire.available() < 2) {
      break;
    }
    uint8_t t = (uint8_t)Wire.read();
    uint8_t p = (uint8_t)Wire.read();
    (void)p;
    switch (t) {
      case PANEL_EVT_ENC_CW:
        encoderDelta(+1);
        break;
      case PANEL_EVT_ENC_CCW:
        encoderDelta(-1);
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
      case PANEL_EVT_SD:
      default:
        break;
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
  if (!gPanelReady) {
    return;
  }
  if (gLcdWelcomed) {
    return;
  }
  if (!wifiOk || !mqttOk) {
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
  if (!gPanelBrowseDirty && (nowMs - gLastBrowseDrawMs) < PANEL_BROWSE_REFRESH_MS) {
    return;
  }
  gPanelBrowseDirty = false;
  gLastBrowseDrawMs = nowMs;

  const uint8_t ch = gUiCh;
  const int pin = CH_PIN[ch];
  const bool on = (digitalRead(pin) == HIGH);
  const bool isAuto = chAuto[ch];

  char line0[21];
  char line1[21];
  char line2[21];
  char line3[21];
  snprintf(line0, sizeof(line0), "%s (%s)", CH_LABEL_KO[ch], chPinLabel(ch));
  snprintf(line1, sizeof(line1), "MODE:%s", isAuto ? "AUTO" : "MAN ");
  snprintf(line2, sizeof(line2), "STATE:%s", on ? "ON " : "OFF");
  snprintf(line3, sizeof(line3), "CH%u/%u Dial Nxt Push",
           (unsigned)(ch + 1), (unsigned)CH_COUNT);

  panelClear();
  panelPrintLine(0, line0);
  panelPrintLine(1, line1);
  panelPrintLine(2, line2);
  panelPrintLine(3, line3);
}

// (LCD + 엔코더 UI 구현은 chManual/chState 선언 이후로 이동)

// 채널별 수동 상태(0/1)
static bool chManual[CH_COUNT] = { false, false, false, false, false, false, false, false, false, false };

// 채널별 주기(ON/OFF ms) 및 타이머
static uint32_t chOnMs[CH_COUNT]  = { 0, 0, 30000, 30000, 0, 30000, 30000, 0, 0, 0 };
static uint32_t chOffMs[CH_COUNT] = { 0, 0, 90000, 90000, 0, 90000, 90000, 0, 0, 0 };
static uint32_t chPrevMs[CH_COUNT] = { 0,0,0,0,0,0,0,0,0,0 };
static bool chState[CH_COUNT] = { false, false, false, false, false, false, false, false, false, false };

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
  if (chIsRemote(ch)) {
    // FAN: Trigorilla로 I2C 전달(임시 FAN 핀)
    const uint8_t bit =
      (ch == CH_FAN_A1) ? 0x01 :
      (ch == CH_FAN_B1) ? 0x02 :
      0x04;
    if (on) gRemoteFanMask |= bit;
    else gRemoteFanMask &= (uint8_t)~bit;
    panelSetFansMask(gRemoteFanMask);
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
    panelClear();
    panelPrintLine(0, line0);
    panelPrintLine(1, line1);
    panelPrintLine(2, line2);
    panelPrintLine(3, line3);
    return;
  }

  // 설정 변경 모드(EDIT)
  snprintf(line0, sizeof(line0), "%s (%s)", CH_LABEL_KO[gUiCh], chPinLabel(gUiCh));
  snprintf(line1, sizeof(line1), "MODE: SET (EDIT)");
  snprintf(line2, sizeof(line2), "OUT:%s", gUiPickOn ? "ON " : "OFF");
  snprintf(line3, sizeof(line3), "Dial:On/Off Push:OK");
  panelClear();
  panelPrintLine(0, line0);
  panelPrintLine(1, line1);
  panelPrintLine(2, line2);
  panelPrintLine(3, line3);
}

static void encoderDelta(int8_t d) {
  if (d == 0) {
    return;
  }
  if (gUiMode == UI_BROWSE) {
    uint8_t prevCh = gUiCh;
    int16_t n = (int16_t)gUiCh + (d > 0 ? 1 : -1);
    if (n < 0) {
      n = (int16_t)CH_COUNT - 1;
    }
    if (n >= (int16_t)CH_COUNT) {
      n = 0;
    }
    gUiCh = (uint8_t)n;
    gUiPickOn = (digitalRead(CH_PIN[gUiCh]) == HIGH);
    if (prevCh != gUiCh && gLcdWelcomed &&
        (int32_t)(millis() - gLcdWelcomeAtMs) >= (int32_t)PANEL_WELCOME_MS) {
      beepShort();
      gPanelBrowseDirty = true;
    }
  } else {
    bool prev = gUiPickOn;
    gUiPickOn = !gUiPickOn;
    if (prev != gUiPickOn) {
      beepShort();
    }
  }
}

static void panelHandleClick(uint32_t nowMs) {
  if (nowMs - gBtnLastMs < 220) {
    return;
  }
  gBtnLastMs = nowMs;
  if (gUiMode == UI_BROWSE) {
    if (!gLcdWelcomed || (int32_t)(millis() - gLcdWelcomeAtMs) < (int32_t)PANEL_WELCOME_MS) {
      return;
    }
    gUiMode = UI_EDIT;
    gUiPickOn = (digitalRead(CH_PIN[gUiCh]) == HIGH);
    beepShort();
  } else {
    uiApplySelection(gUiCh, gUiPickOn);
    beepLong();
    publishTelemetry();
    gUiMode = UI_BROWSE;
    gPanelBrowseDirty = true;
  }
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

// 내장 12x8 LED 매트릭스 — WiFi/MQTT/펌프·LED 상태 표시
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

// 8×12 패턴: 'O'=켜짐, 그 외=끔 (열 0이 왼쪽)
static void matBlitPattern8x12(const char pat[8][13]) {
  for (int r = 0; r < 8; r++) {
    for (int c = 0; c < 12; c++) {
      char ch = pat[r][c];
      gMatFrame[r][c] = (ch == 'O' || ch == 'o') ? 1u : 0u;
    }
  }
}

// WiFi만 연결
static const char MAT_WIFI_ONLY[8][13] = {
  "XXXXXXXXXOOO",
  "XXXXXXXXOOXX",
  "XXOXXXXOOXXX",
  "XXOXXXOOXXXX",
  "XXXOXOOXXXXX",
  "XXXXOXXXXXXX",
  "XXXXXXXXXXXX",
  "XXXXXXXXXXXX",
};

// WiFi + MQTT
static const char MAT_WIFI_MQTT[8][13] = {
  "XXXXXXXXXOOO",
  "XXXXXXXXOOXX",
  "XXOXXXXOOXXX",
  "XXOXXXOOXXXX",
  "XXXOXOOXXXXX",
  "XXXXOXXXXXXX",
  "OOOOOXOOOOOO",
  "OXOOOOXOXXOX",
};

static void matRenderStatus(bool wifiOk, bool mqttOk) {
  matClear();
  if (wifiOk && mqttOk) {
    matBlitPattern8x12(MAT_WIFI_MQTT);
  } else if (wifiOk) {
    matBlitPattern8x12(MAT_WIFI_ONLY);
  } else if (mqttOk) {
    matBlitPattern8x12(MAT_WIFI_ONLY);
  } else {
    matPixel(4, 3, 1);
    matPixel(4, 8, 1);
    matPixel(5, 4, 1);
    matPixel(5, 5, 1);
    matPixel(5, 6, 1);
    matPixel(5, 7, 1);
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
    const bool isPump = (i == CH_PUMP_A1 || i == CH_PUMP_A2 || i == CH_PUMP_B1 || i == CH_PUMP_B2);
    const bool isFan = (i == CH_FAN_A1 || i == CH_FAN_B1 || i == CH_FAN_B2);
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
    pinMode(CH_PIN[i], OUTPUT);
  }
  allOff();

  Serial.begin(BAUD);
  delay(200);

  Wire.begin();
  delay(2);
  gPanelReady = panelProbe();
  if (!gPanelReady) {
    Serial.println(F("I2C 패널(R3) 응답 없음 — 릴레이만 동작"));
  } else {
    panelPrintLine(0, "CronusFarm");
    panelPrintLine(1, "부팅중...");
  }

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
  // I2C 패널은 전원/리셋 타이밍으로 setup()에서 프로브가 실패할 수 있어,
  // loop에서 주기적으로 재시도하여 “부팅 화면에서 멈춤” 상태를 자동 복구합니다.
  if (!gPanelReady && (int32_t)(now - gNextPanelProbeMs) >= 0) {
    gNextPanelProbeMs = now + 1000;
    if (panelProbe()) {
      gPanelReady = true;
      gLcdWelcomed = false;
      gPanelBrowseDirty = true;
      panelClear();
      panelPrintLine(0, "CronusFarm");
      panelPrintLine(1, "패널 연결됨");
    }
  }
  panelPollEvents(now);

  // I2C 스캔(진단용): 버스에 어떤 장치라도 잡히는지 확인 (5초마다)
  static uint32_t nextScanMs = 0;
  if (now - nextScanMs >= 5000) {
    nextScanMs = now;
    uint8_t found = 0;
    uint8_t first = 0;
    for (uint8_t addr = 1; addr < 127; addr++) {
      Wire.beginTransmission(addr);
      const uint8_t ec = (uint8_t)Wire.endTransmission();
      if (ec == 0) {
        found++;
        if (first == 0) first = addr;
      }
    }
    Serial.print(F("[I2C-SCAN] found="));
    Serial.print(found);
    if (found) {
      Serial.print(F(" first=0x"));
      if (first < 16) Serial.print('0');
      Serial.print(first, HEX);
    }
    Serial.println();
  }

  // 채널별 AUTO/수동 처리
  // - AUTO=1: 해당 채널이 펌프류면 on/off 주기로 토글, LED류면 수동(기본 OFF) 유지
  // - AUTO=0: chManual[] 값대로 출력
  for (uint8_t i = 0; i < CH_COUNT; i++) {
    const bool isPump = (i == CH_PUMP_A1 || i == CH_PUMP_A2 || i == CH_PUMP_B1 || i == CH_PUMP_B2);
    const bool isFan = (i == CH_FAN_A1 || i == CH_FAN_B1 || i == CH_FAN_B2);

    if (!chAuto[i]) {
      if (chIsRemote(i)) {
        const bool on = chManual[i];
        const uint8_t bit =
          (i == CH_FAN_A1) ? 0x01 :
          (i == CH_FAN_B1) ? 0x02 :
          0x04;
        if (on) gRemoteFanMask |= bit;
        else gRemoteFanMask &= (uint8_t)~bit;
        panelSetFansMask(gRemoteFanMask);
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
        const uint8_t bit =
          (i == CH_FAN_A1) ? 0x01 :
          (i == CH_FAN_B1) ? 0x02 :
          0x04;
        gRemoteFanMask &= (uint8_t)~bit;
        panelSetFansMask(gRemoteFanMask);
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

