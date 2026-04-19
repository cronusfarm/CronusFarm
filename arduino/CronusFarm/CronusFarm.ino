/*
  CronusFarm - UNO R4 WiFi (MQTT 제어용 기본 스케치)

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

  핀(권장: 배선 단순/확장 용이)
  - LED_A1 : D2
  - LED_A2 : D3
  - PUMP_A1: D4
  - PUMP_A2: D5
  - LED_B1 : D6
  - PUMP_B1: D7
  - PUMP_B2: D8

  내장 LED 매트릭스(12x8)
  - WiFi만 연결: 상단 RSSI(안테나 막대 1~4단계)
  - WiFi+MQTT 연결: 상단 체크(V, 정상 가동)
  - WiFi 끊김: 상단 경고 패턴
  - 하단: 펌프 B1 / B2 / LED 각각 2x2 점(켜질 때만)
*/

#include "RTC.h"
#include <EEPROM.h>
#include <WiFiS3.h>
#include <ArduinoMqttClient.h>
#include <string.h>
#include "Arduino_LED_Matrix.h"

// `secrets.h.example`을 복사해서 `secrets.h`를 만든 뒤 값을 채우세요.
#include "secrets.h"

static const uint32_t BAUD = 115200;

static const int LED_A1 = 2;
static const int LED_A2 = 3;
static const int PUMP_A1 = 4;
static const int PUMP_A2 = 5;
static const int LED_B1 = 6;
static const int PUMP_B1 = 7;
static const int PUMP_B2 = 8;

// 채널 정의(표시/제어용)
enum Channel : uint8_t {
  CH_LED_A1 = 0,
  CH_LED_A2 = 1,
  CH_PUMP_A1 = 2,
  CH_PUMP_A2 = 3,
  CH_LED_B1 = 4,
  CH_PUMP_B1 = 5,
  CH_PUMP_B2 = 6,
  CH_COUNT = 7
};

static const int CH_PIN[CH_COUNT] = {
  LED_A1, LED_A2, PUMP_A1, PUMP_A2, LED_B1, PUMP_B1, PUMP_B2
};

static const char* const CH_KEY[CH_COUNT] = {
  "led_a1", "led_a2", "pump_a1", "pump_a2", "led_b1", "pump_b1", "pump_b2"
};

static const char* const CH_LABEL_KO[CH_COUNT] = {
  "LED A1", "LED A2", "PUMP A1", "PUMP A2", "LED B1", "PUMP B1", "PUMP B2"
};

// 채널별 AUTO(1)/수동(0)
static bool chAuto[CH_COUNT] = {
  false, false, true, true, false, true, true
};

// 채널별 수동 상태(0/1)
static bool chManual[CH_COUNT] = { false, false, false, false, false, false, false };

// 채널별 주기(ON/OFF ms) 및 타이머
static uint32_t chOnMs[CH_COUNT]  = { 0, 0, 30000, 30000, 0, 30000, 30000 };
static uint32_t chOffMs[CH_COUNT] = { 0, 0, 90000, 90000, 0, 90000, 90000 };
static uint32_t chPrevMs[CH_COUNT] = { 0,0,0,0,0,0,0 };
static bool chState[CH_COUNT] = { false, false, false, false, false, false, false };

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

// RSSI(dBm) → 안테나 막대 단계(1~4). 비정상 값은 중간으로 표시.
static int wifiRssiToBars(int rssi) {
  if (rssi >= 0 || rssi < -100) return 2;
  if (rssi >= -55) return 4;
  if (rssi >= -65) return 3;
  if (rssi >= -75) return 2;
  return 1;
}

// WiFi 연결됨 — RSSI에 따라 세로 막대 개수·높이(1~4단계)
static void matDrawWifiRssiBars(int bars) {
  const int baseR = 5;
  struct {
    int c;
    int h;
  } col[] = { { 3, 2 }, { 5, 3 }, { 7, 4 }, { 9, 5 } };
  if (bars < 1) bars = 1;
  if (bars > 4) bars = 4;
  for (int i = 0; i < bars; i++) {
    for (int k = 0; k < col[i].h; k++) {
      matPixel(baseR - k, col[i].c, 1);
    }
  }
}

// 시스템 정상(WiFi+MQTT) — 체크 표시
static void matDrawOkIcon() {
  // 12열(0..11) 기준 좌우 반전(가로 미러링)
  matPixel(1, 8, 1);
  matPixel(2, 7, 1);
  // 체크 오른쪽 사선(두 점) 복구
  matPixel(3, 6, 1);
  matPixel(4, 5, 1);
  matPixel(4, 3, 1);
  matPixel(5, 4, 1);
  // 좌표 표기는 (행×열), 1부터 시작이라고 가정:
  // 3×6 -> 4×3, 4×5 -> 5×4 를 0-based로 변환해 반영
  // (2,5) -> (3,2), (3,4) -> (4,3)
  matPixel(3, 2, 1);
}

// 하단: B1(왼쪽), B2(가운데), LED(오른쪽) — 켜지면 2x2 블록
static void matDrawIoRow(bool b1, bool b2, bool led) {
  const int row0 = 6;
  const int row1 = 7;
  if (b1) {
    matPixel(row0, 1, 1);
    matPixel(row0, 2, 1);
    matPixel(row1, 1, 1);
    matPixel(row1, 2, 1);
  }
  if (b2) {
    matPixel(row0, 5, 1);
    matPixel(row0, 6, 1);
    matPixel(row1, 5, 1);
    matPixel(row1, 6, 1);
  }
  if (led) {
    matPixel(row0, 9, 1);
    matPixel(row0, 10, 1);
    matPixel(row1, 9, 1);
    matPixel(row1, 10, 1);
  }
}

static void matRenderStatus(bool wifiOk, bool mqttOk, bool b1, bool b2, bool led, bool mqttWaitPulse) {
  matClear();
  if (mqttOk && wifiOk) {
    matDrawOkIcon();
  } else if (wifiOk) {
    int rssi = WiFi.RSSI();
    matDrawWifiRssiBars(wifiRssiToBars(rssi));
    if (mqttWaitPulse) {
      matPixel(0, 0, 1);
      matPixel(0, 11, 1);
    }
  } else {
    matPixel(4, 3, 1);
    matPixel(4, 8, 1);
    matPixel(5, 4, 1);
    matPixel(5, 5, 1);
    matPixel(5, 6, 1);
    matPixel(5, 7, 1);
  }
  matDrawIoRow(b1, b2, led);
  gMatrix.renderBitmap(gMatFrame, 8, 12);
}

static void matrixTick(uint32_t nowMs, bool wifiOk, bool mqttOk, bool b1, bool b2, bool led) {
  static bool prevW = false;
  static bool prevM = false;
  static bool prevB1 = false;
  static bool prevB2 = false;
  static bool prevL = false;
  static int prevRssiBars = -1;
  static bool first = true;
  static uint32_t prevSlice = 0xFFFFFFFFu;

  const uint32_t slice = nowMs / 450u;
  const bool mqttWait = wifiOk && !mqttOk;
  const int curRssiBars = (wifiOk && !mqttOk) ? wifiRssiToBars(WiFi.RSSI()) : -1;
  const bool rssiDiff = (curRssiBars >= 0) && (curRssiBars != prevRssiBars);
  const bool logicDiff =
    first || (wifiOk != prevW) || (mqttOk != prevM) || (b1 != prevB1) || (b2 != prevB2) || (led != prevL);
  const bool animDiff = mqttWait && (slice != prevSlice);

  if (!logicDiff && !animDiff && !rssiDiff) {
    return;
  }

  if (logicDiff) {
    first = false;
    prevW = wifiOk;
    prevM = mqttOk;
    prevB1 = b1;
    prevB2 = b2;
    prevL = led;
  }
  prevSlice = slice;
  if (curRssiBars >= 0) {
    prevRssiBars = curRssiBars;
  } else {
    prevRssiBars = -1;
  }

  const bool pulse = mqttWait && ((slice & 1u) != 0);
  matRenderStatus(wifiOk, mqttOk, b1, b2, led, pulse);
}

// 핀/WiFi/MQTT 상태로 매트릭스 즉시 갱신(setup·WiFi 성공 직후 등, loop 전에도 호출 가능)
static void matrixShowFromPins() {
  matRenderStatus(
    WiFi.status() == WL_CONNECTED,
    mqtt.connected(),
    digitalRead(PUMP_B1) == HIGH,
    digitalRead(PUMP_B2) == HIGH,
    digitalRead(LED_B1) == HIGH,
    false
  );
}

static void allOff() {
  for (uint8_t i = 0; i < CH_COUNT; i++) {
    digitalWrite(CH_PIN[i], LOW);
    chState[i] = false;
  }
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
    int v = (digitalRead(CH_PIN[i]) == HIGH) ? 1 : 0;
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

  gMatrix.begin();
  // begin 직후 한 번 그리기(MQTT 대기로 setup이 안 끝나도 이후 WiFi 성공 시 다시 갱신)
  matRenderStatus(false, false, false, false, false, false);

  RTC.begin();
  RTCTime startTime(16, Month::APRIL, 2026, 17, 30, 0, DayOfWeek::THURSDAY, SaveLight::SAVING_TIME_INACTIVE);
  RTC.setTime(startTime);

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

  // 채널별 AUTO/수동 처리
  // - AUTO=1: 해당 채널이 펌프류면 on/off 주기로 토글, LED류면 수동(기본 OFF) 유지
  // - AUTO=0: chManual[] 값대로 출력
  for (uint8_t i = 0; i < CH_COUNT; i++) {
    const bool isPump = (i == CH_PUMP_A1 || i == CH_PUMP_A2 || i == CH_PUMP_B1 || i == CH_PUMP_B2);

    if (!chAuto[i]) {
      digitalWrite(CH_PIN[i], chManual[i] ? HIGH : LOW);
      chState[i] = chManual[i];
      continue;
    }

    if (!isPump) {
      digitalWrite(CH_PIN[i], LOW);
      chState[i] = false;
      continue;
    }

    uint32_t nowMs = millis();
    uint32_t interval = chState[i] ? chOnMs[i] : chOffMs[i];
    if (interval < 200) interval = 200;
    if (nowMs - chPrevMs[i] >= interval) {
      chPrevMs[i] = nowMs;
      chState[i] = !chState[i];
      digitalWrite(CH_PIN[i], chState[i] ? HIGH : LOW);
    }
  }

  uint32_t now = millis();
  if (now - lastTelemetryMs >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryMs = now;
    publishTelemetry();
  }

  bool outB1 = digitalRead(PUMP_B1) == HIGH;
  bool outB2 = digitalRead(PUMP_B2) == HIGH;
  bool outLed = digitalRead(LED_B1) == HIGH;
  bool wifiOk = (WiFi.status() == WL_CONNECTED);
  bool mqttOk = mqtt.connected();
  matrixTick(now, wifiOk, mqttOk, outB1, outB2, outLed);
}

