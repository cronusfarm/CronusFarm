/*
  2026.05.06 20:15:00
  2026.5.3 펌프 하드 가드(연속 ON·쿨다운·최소 OFF)·tele `G:` — docs/cronusfarm_settings_schema.md
  2026.5.2 tele 버퍼/MQTT TX CRONUS_TELE_PAYLOAD_MAX(2048) 정렬 — 잘림 방지
  2026.4.26 수정
  CronusFarm - UNO R4 WiFi (메인 MQTT·릴레이·I2C 마스터)
  패널(RepRap 2004A)은 UNO R3 `CronusFarmPanel` 스케치 — 별도 업로드

  목표
  - Node-RED(UI/자동화) ↔ Arduino 통신을 **MQTT(WiFi)** 로 전환
  - USB Serial: 업로드/디버그 + Pi USB 프로비저닝(wifi_set / wifi_clear / wifi_status)

  토픽 규약(DEVICE_ID=cronusfarm-01 예시)
  - 명령 수신:   cronusfarm/cronusfarm-01/cmd
  - 상태 발행:   cronusfarm/cronusfarm-01/tele
  - 온라인 발행: cronusfarm/cronusfarm-01/status  (online/offline)
  - Pi SSID 동기: MQTT_TOPIC_PI_WIFI_SSID — `SSID` 또는 `SSID 비밀번호`(첫 공백 기준, 목록 외 등록)
  - Pi USB 시리얼(115200): `wifi_set <SSID> <비밀번호>` / `wifi_clear` / `wifi_status` — scripts/pi-serial-wifi-provision.sh
  - Pi→R4 RTC 동기: cmd `rtc_local=YYYYMMDDHHmmss` (Pi `date` 로컬 시각 14자리, scripts/pi-mqtt-publish-rtc-to-r4.sh)

  페이로드(간단/라이브러리 최소화)
  - cmd:  아래 2가지 형식을 모두 지원
    1) 단일 문자 명령(Serial 코드 호환): "M", "m", "A", "a", "B", "b", "C", "c", "N30", "F90"
    2) key=value 토큰(공백 구분): "auto=1 b1=0 b2=1 led=1 on=30 off=90"
  - tele: "S:... | A:... | T:... | W:... | G:..." (채널·WiFi·펌프 가드 — docs/cronusfarm_settings_schema.md)
  - tele 백업: MQTT 실패 시 HTTP POST → Pi `/farm/cronusfarm-sqlite/ingest/tele` (docs/cronusfarm_mqtt_stability.md §8.1)

  핀(UNO R4 WiFi 메인 — `docs/cronusfarm_hardware_pins.md` 동기)
  - 패널 링크: I2C SDA=A4, SCL=A5 → R3 슬레이브 0x38 (GND 공통). 패널 UART 미사용.
  - A Bed: LED_A1 D2, LED_A2 D3, PUMP_A1 D4, PUMP_A2 D5
  - B Bed: LED_B1 D6, PUMP_B1 D7, PUMP_B2 D8, LED_B2(여분) D13
  - FAN: FAN_A1 D9, FAN_A2 D10, FAN_B1 D11, FAN_B2 D12
  - Pump C/D: PUMP_C1 A0, PUMP_C2 A1, PUMP_D1 A2, PUMP_D2 A3

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
#include <stdarg.h>
#include <Wire.h>
#include "Arduino_LED_Matrix.h"
// R4(마스터) ↔ R3(슬레이브) 패널(I2C) 프로토콜
#include "panel_i2c_protocol.h"
// `secrets.h.example`을 복사해서 `secrets.h`를 만든 뒤 값을 채우세요.
#include "secrets.h"
#include "cf_schedule_types.h"
#include "cf_builtin_schedule.h"

#ifndef BRIDGE_HTTP_HOST
#define BRIDGE_HTTP_HOST MQTT_HOST
#endif
#ifndef BRIDGE_HTTP_PORT
#define BRIDGE_HTTP_PORT 80
#endif
#ifndef BRIDGE_HTTP_PATH
#define BRIDGE_HTTP_PATH "/farm/cronusfarm-sqlite/ingest/tele"
#endif
#ifndef CRONUS_HTTP_TELE_BACKUP
#define CRONUS_HTTP_TELE_BACKUP 1
#endif
#ifndef CRONUSFARM_MQTT_ENABLE
#define CRONUSFARM_MQTT_ENABLE 1
#endif

static const uint32_t BAUD = 115200;

/** tele 한 줄(S|A|T|W) 최대 길이. `ArduinoMqttClient::setTxPayloadSize`와 반드시 동일 값 유지.
 *  값이 작으면 MQTT publish 시 끝이 잘려 Node-RED tele(raw)·tele(요약)이 중간에 끊김. */
#define CRONUS_TELE_PAYLOAD_MAX 2048

/** 펌프 하드 가드 — 연속 ON 상한·쿨다운·최소 OFF (docs/cronusfarm_settings_schema.md). 값은 문서·코드 동기화. */
static const uint32_t PUMP_GUARD_MAX_ON_MS = 1800ul * 1000ul;   // T_max_on : 30분
static const uint32_t PUMP_GUARD_COOLDOWN_MS = 60ul * 1000ul;    // T_cool   : 60초
static const uint32_t PUMP_GUARD_MIN_OFF_MS = 10ul * 1000ul;   // T_min_off: 10초

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
static const int FAN_A1 = 9;
static const int FAN_A2 = 10;
static const int FAN_B1 = 11;
static const int FAN_B2 = 12;
static const int LED_B2 = 13;
static const int PUMP_C1 = A0;
static const int PUMP_C2 = A1;
static const int PUMP_D1 = A2;
static const int PUMP_D2 = A3;

// 패널(UNO R3) 상태 — I2C 링크/환영/브라우즈 화면 상태 추적
static bool gPanelReady = false;
static bool gLcdWelcomed = false;
static uint32_t gLcdWelcomeAtMs = 0;
// millis() 경계·언더플로로 isInWelcomeWindow만으로는 환영이 안 끝난 것처럼 보일 때 푸시가 Edit에 못 들어가는 것 방지
static bool gLcdWelcomeBypass = false;
static uint32_t gLastLcdRtcMs = 0;
// 브라우즈·EDIT: 루프가 느릴 때 큐에 쌓인 엔코더를 한 번에 여러 번 적용하지 않도록
static uint32_t gLastEncBrowseApplyMs = 0;
// 패널 브라우즈 화면 갱신(엔코더·적용 직후 + 주기적 STATE 반영)
static bool gPanelBrowseDirty = true;
static uint32_t gLastBrowseDrawMs = 0;
// 환영/부팅 상태에서 "푸시=EDIT"로 들어가 버리는 것을 막기 위해,
// 실제로 브라우즈 화면(4줄)이 한 번이라도 그려졌는지 추적합니다.
static bool gPanelBrowseShown = false;
static const uint32_t PANEL_WELCOME_MS = 5000;
// 채널 브라우즈에서 엔코더·푸시 없음 → 환영 화면 복귀
static const uint32_t PANEL_BROWSE_IDLE_MS = 600000ul;
static uint32_t gPanelLastUserInputMs = 0;
// 브라우즈 10분 무입력 → 환영(D) 유지(5초 후 자동 브라우즈 복귀 방지)
static bool gPanelIdleWelcomeHold = false;
// I2C 링크 직후 스플래시(CronusFarm/WiFi/MQTT)가 같은 루프에서 대기 화면에 덮이지 않게 최소 표시
static const uint32_t PANEL_LINK_SPLASH_MIN_MS = 5000;
// WiFi 미연결 대기 화면(Waiting link) 최소 유지 — 다음 화면(환영) 전에 눈으로 확인 가능
static const uint32_t PANEL_LINK_WAIT_MIN_MS = 5000;
static uint32_t gPanelLinkSplashUntilMs = 0;
static uint32_t gPanelWaitMinUntilMs = 0;
static const uint32_t PANEL_BROWSE_REFRESH_MS = 800;
// 브라우즈에서 입력 먹통처럼 보일 때 리셋 없이: 푸시 2회(0.45초 이내) → I2C·LCD 소프트 복구
static const uint32_t PANEL_DOUBLE_CLICK_MS = 450u;
static const uint32_t PANEL_SOFT_RECOVER_COOLDOWN_MS = 2500u;
static uint32_t gPanelLastClickMs = 0;
static uint32_t gPanelLastSoftRecoverMs = 0;
static bool gPanelUiDirty = true;          // EDIT 화면용: dirty일 때만 4줄 강제 갱신
static uint32_t gLastEditDrawMs = 0;
static const uint32_t PANEL_EDIT_REFRESH_MS = 400;
// 패널 LCD 라인 캐시(중복 전송 감소)
static bool gPanelLineInit[4] = { false, false, false, false };
static char gPanelLineCache[4][21];

// 패널 이벤트(엔코더/클릭) 수신 진단
static uint32_t gPanelLastEvtMs = 0;
static uint32_t gPanelEvtCount = 0;

// 패널 링크(권장: I2C 전용)
// - 목적: R3 SoftwareSerial(UART) 반이중(RX/TX)로 인한 LCD 줄 깨짐/이벤트 유실을 구조적으로 제거
// - 배선:
//   * R4 SDA(A4) ↔ R3 SDA(A4)
//   * R4 SCL(A5) ↔ R3 SCL(A5)
//   * GND 공통(필수)
// - R3는 I2C 슬레이브(0x38)로 동작하며, LCD/엔코더 이벤트를 I2C로만 처리합니다.
#define CF_PANEL_LINK_UART 0
#define CF_PANEL_LINK_I2C 1

#if CF_PANEL_LINK_I2C
static uint32_t gLastPanelI2cPingMs = 0;
// I2C 진단(tele 디버그용)
static uint8_t gPanelI2cLastEndTxRc = 255;
static int gPanelI2cLastReqGot = -1;
static uint32_t gPanelI2cLastRxMs = 0;
static uint8_t gPanelI2cMissStreak = 0;

static bool panelI2cPing(uint32_t nowMs) {
  // 너무 자주 두드리면 버스가 지저분해질 수 있어 간격을 둡니다.
  if (gLastPanelI2cPingMs != 0 && (nowMs - gLastPanelI2cPingMs) < 300) {
    return false;
  }
  gLastPanelI2cPingMs = nowMs;

  Wire.beginTransmission(PANEL_I2C_ADDR);
  Wire.write((uint8_t)PANEL_CMD_CLEAR);
  const uint8_t rc = (uint8_t)Wire.endTransmission();
  gPanelI2cLastEndTxRc = rc;
  // endTransmission() == 0 이면 ACK(슬레이브 응답)로 판단
  return (rc == 0);
}
#endif

// UART 관련 전송 제어
#if CF_PANEL_LINK_UART
// SoftwareSerial(R3) 안정성을 위해 보수적으로 낮춤
static const uint32_t CF_PANEL_UART_BAUD = 9600;
#define CF_PANEL_UART Serial1
static char gPanelRxLine[96];
static uint8_t gPanelRxLen = 0;
static uint32_t gPanelLastTxUs = 0;
static void panelUartTxPace() {
  // UART 스트림이 섞여 라인 경계가 흔들리는 문제를 완화하기 위한 전송 간격 제한
  // R3 SoftwareSerial RX가 줄 단위로 쉴 틈을 주려면 L, 명령 사이 간격을 넉넉히
  const uint32_t minGapUs = 14000; // ~14ms (9600 + SS 여유)
  const uint32_t nowUs = (uint32_t)micros();
  if (gPanelLastTxUs != 0) {
    const uint32_t gap = nowUs - gPanelLastTxUs;
    if (gap < minGapUs) {
      delayMicroseconds((int)(minGapUs - gap));
    }
  }
  gPanelLastTxUs = (uint32_t)micros();
}
#endif


static void panelClear();
static void panelPrintLine(uint8_t row, const char* text);
static void panelBeepShort();
static void panelBeepLong();
static void panelSetBlink(uint8_t row, uint8_t col, bool on);
static void panelPollEvents(uint32_t nowMs);
static void lcdWelcomeIfOk(uint32_t nowMs, bool wifiOk, bool mqttOk);
static void panelNoteUserInput(uint32_t nowMs);
static void panelReturnToWelcome(uint32_t nowMs);
static void panelBrowseIdleCheck(uint32_t nowMs);
static void lcdBrowseDraw(uint32_t nowMs);

// ============================================================
// LCD + 엔코더 UI는 채널 정의/배열 이후에 선언(선언 순서 의존성 방지)
enum UiMode : uint8_t { UI_BROWSE = 0, UI_EDIT = 1 };
static UiMode gUiMode = UI_BROWSE;
static uint8_t gUiCh = 0;
// EDIT SET: 0=OFF, 1=ON, 2=AUTO(chAuto·스케줄/펌웨어 자동 루프)
static uint8_t gUiEditSet = 0;
static uint8_t gUiEditOrigSet = 0;

static uint32_t gBtnLastMs = 0;

static void beepShort();
static void beepLong();
static void uiApplyEditSelection(uint8_t ch, uint8_t setVal);
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
  CH_FAN_A1 = 7,
  CH_FAN_A2 = 8,
  CH_FAN_B1 = 9,
  CH_FAN_B2 = 10,
  CH_PUMP_C1 = 11,
  CH_PUMP_C2 = 12,
  CH_PUMP_D1 = 13,
  CH_PUMP_D2 = 14,
  CH_LED_B2 = 15,
  CH_COUNT = 16
};

// 다이얼로 UI를 순환할 채널 순서(항상 고정)
// V0.7+(16채널) 브라우즈 순서 고정: CH1→CH16 한 칸씩만 이동(uiNextCh)
static const uint8_t UI_CH_ORDER[CH_COUNT] = {
  CH_LED_A1,   // CH1
  CH_LED_A2,   // CH2
  CH_PUMP_A1,  // CH3
  CH_PUMP_A2,  // CH4
  CH_FAN_A1,   // CH5
  CH_FAN_A2,   // CH6
  CH_LED_B1,   // CH7
  CH_LED_B2,   // CH8
  CH_PUMP_B1,  // CH9
  CH_PUMP_B2,  // CH10
  CH_FAN_B1,   // CH11
  CH_FAN_B2,   // CH12
  CH_PUMP_C1,  // CH13
  CH_PUMP_C2,  // CH14
  CH_PUMP_D1,  // CH15
  CH_PUMP_D2,  // CH16
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

// 환영 5초 구간 + 사용자가 환영을 끊은 뒤(gLcdWelcomeBypass)에는 시간 비교 무시
static inline bool isInWelcomeWindow() {
  return gLcdWelcomed && !gLcdWelcomeBypass &&
         (uint32_t)(millis() - gLcdWelcomeAtMs) < (uint32_t)PANEL_WELCOME_MS;
}

static void forceStartFromCh1();

// 로컬 GPIO 제어 채널 핀 매핑 (V0.7: 전부 R4 로컬 제어)
static const int CH_PIN[CH_COUNT] = {
  LED_A1,   // CH_LED_A1
  LED_A2,   // CH_LED_A2
  LED_B1,   // CH_LED_B1
  PUMP_A1,  // CH_PUMP_A1
  PUMP_A2,  // CH_PUMP_A2
  PUMP_B1,  // CH_PUMP_B1
  PUMP_B2,  // CH_PUMP_B2
  FAN_A1,   // CH_FAN_A1
  FAN_A2,   // CH_FAN_A2
  FAN_B1,   // CH_FAN_B1
  FAN_B2,   // CH_FAN_B2
  PUMP_C1,  // CH_PUMP_C1
  PUMP_C2,  // CH_PUMP_C2
  PUMP_D1,  // CH_PUMP_D1
  PUMP_D2,  // CH_PUMP_D2
  LED_B2,   // CH_LED_B2
};

static const char* const CH_KEY[CH_COUNT] = {
  "led_a1",
  "led_a2",
  "led_b1",
  "pump_a1",
  "pump_a2",
  "pump_b1",
  "pump_b2",
  "fan_a1",
  "fan_a2",
  "fan_b1",
  "fan_b2",
  "pump_c1",
  "pump_c2",
  "pump_d1",
  "pump_d2",
  "led_b2",
};

static const char* const CH_LABEL_KO[CH_COUNT] = {
  "LED A1",  "LED A2",  "LED B1",
  "PUMP A1", "PUMP A2", "PUMP B1", "PUMP B2",
  "FAN A1",  "FAN A2",  "FAN B1",  "FAN B2",
  "PUMP C1", "PUMP C2", "PUMP D1", "PUMP D2",
  "LED B2",
};

// 채널별 AUTO(1)/수동(0) — 기본 자동(스케줄 적용). 부팅 점검 직후 AUTO.
static bool chAuto[CH_COUNT] = {
  true, true, true, true, true, true, true, true,
  true, true, true, true, true, true, true, true,
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
    case CH_FAN_A1: return "D9";
    case CH_FAN_A2: return "D10";
    case CH_FAN_B1: return "D11";
    case CH_FAN_B2: return "D12";
    case CH_PUMP_C1: return "A0";
    case CH_PUMP_C2: return "A1";
    case CH_PUMP_D1: return "A2";
    case CH_PUMP_D2: return "A3";
    case CH_LED_B2: return "D13";
    default: return "?";
  }
}

// 채널별 수동 상태·타이머·출력 — lcdBrowseDraw·패널 UI보다 먼저 두어 컴파일 순서 충족
static bool chManual[CH_COUNT] = {
  false, false, false,
  false, false, false, false,
  false, false, false, false,
  false, false, false, false,
  false
};
// MQTT(cmd)와 패널(UI) 동시 제어 시, 패널에서 막 바꾼 상태가 즉시 덮어써져 OFF로 “튀는” 현상 방지용
static uint32_t gUiLocalOverrideAtMs[CH_COUNT] = {
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
};
static const uint32_t UI_LOCAL_OVERRIDE_HOLD_MS = 3000;
// 패널 2004A 엔코더 MAN(OFF/ON) 후 자동 복귀 상한 — Pi channel_manual_hold(60분)와 맞춤
static const uint32_t PANEL_MANUAL_HOLD_MS = 3600000UL;
static uint32_t chPanelManualUntilMs[CH_COUNT] = {
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
};
static uint32_t chOnMs[CH_COUNT]  = {
  0, 0, 0,                 // LED A1,A2,B1
  30000, 30000,            // PUMP A
  30000, 30000,            // PUMP B
  0, 0, 0, 0,              // FAN
  30000, 30000,            // PUMP C
  30000, 30000,            // PUMP D
  0                        // LED B2
};
static uint32_t chOffMs[CH_COUNT] = {
  0, 0, 0,                 // LED A1,A2,B1
  90000, 90000,            // PUMP A
  90000, 90000,            // PUMP B
  0, 0, 0, 0,              // FAN
  90000, 90000,            // PUMP C
  90000, 90000,            // PUMP D
  0                        // LED B2
};
static uint32_t chPrevMs[CH_COUNT] = {
  0,0,0,
  0,0,0,0,
  0,0,0,0,
  0,0,0,0,
  0
};

static bool gBootBuiltinSchedDone = false;
static bool chState[CH_COUNT] = {
  false, false, false,
  false, false, false, false,
  false, false, false, false,
  false, false, false, false,
  false
};

// ---------- Pi 스케줄(SCHED_JSON) — SQLite 브리지가 MQTT cmd로 전달 ----------
static CfSchRule gSchRules[CH_COUNT][CF_SCH_MAX_RULES];
static uint8_t gSchRuleCount[CH_COUNT];
static uint32_t gSchVer[CH_COUNT];
// MQTT 끊김 N ms 이후 cf_builtin_schedule.h(하드코딩)로 강제 전환
static const uint32_t MQTT_OFFLINE_BUILTIN_MS = 5UL * 60UL * 1000UL;
static uint32_t gMqttLastConnectedMs = 0;
static bool gMqttBuiltinOfflineActive = false;

static int cfHexVal(int c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return -1;
}

static void cfUrlDecode(const char* in, char* out, size_t outsz) {
  size_t j = 0;
  if (outsz == 0) return;
  for (size_t i = 0; in[i] && j + 1 < outsz; ) {
    if (in[i] == '%' && cfHexVal((unsigned char)in[i + 1]) >= 0 &&
        cfHexVal((unsigned char)in[i + 2]) >= 0) {
      int a = cfHexVal((unsigned char)in[i + 1]);
      int b = cfHexVal((unsigned char)in[i + 2]);
      out[j++] = (char)((a << 4) | b);
      i += 3;
    } else if (in[i] == '+') {
      out[j++] = ' ';
      ++i;
    } else {
      out[j++] = in[i++];
    }
  }
  out[j] = '\0';
}

static bool cfMinuteInWindow(uint16_t nowMin, uint16_t on, uint16_t off) {
  if (on == off) return false;
  if (on < off) return (nowMin >= on) && (nowMin < off);
  return (nowMin >= on) || (nowMin < off);
}

static bool cfCycleWantOn(uint32_t ons, uint32_t offs, uint32_t secDay) {
  uint32_t per = ons + offs;
  if (per == 0) return false;
  uint32_t ph = secDay % per;
  return ph < ons;
}

static uint8_t cfRtcDowToUiMask(DayOfWeek d) {
  switch (d) {
    case DayOfWeek::SUNDAY: return 1;
    case DayOfWeek::MONDAY: return 2;
    case DayOfWeek::TUESDAY: return 4;
    case DayOfWeek::WEDNESDAY: return 8;
    case DayOfWeek::THURSDAY: return 16;
    case DayOfWeek::FRIDAY: return 32;
    default:
    case DayOfWeek::SATURDAY: return 64;
  }
}

static bool cfParseOneRule(const char* s, CfSchRule* out) {
  memset(out, 0, sizeof(*out));
  out->enabled = 1;
  const bool isCyc = (strstr(s, "\"rule_kind\":\"cycle\"") != nullptr) ||
                     (strstr(s, "\"rule_kind\": \"cycle\"") != nullptr);
  out->kind = isCyc ? (uint8_t)1 : (uint8_t)0;
  const char* p = strstr(s, "\"dow_mask\":");
  if (!p) return false;
  unsigned long dm = strtoul(p + 11, nullptr, 10);
  if (dm > 127) dm = 127;
  out->dow_mask = (uint8_t)dm;
  if (isCyc) {
    p = strstr(s, "\"on_sec\":");
    if (!p) return false;
    out->on_sec = (uint32_t)strtoul(p + 9, nullptr, 10);
    p = strstr(s, "\"off_sec\":");
    if (!p) return false;
    out->off_sec = (uint32_t)strtoul(p + 10, nullptr, 10);
    p = strstr(s, "\"on_min\":");
    if (p) out->on_min = (uint16_t)strtoul(p + 9, nullptr, 10);
    p = strstr(s, "\"off_min\":");
    if (p) out->off_min = (uint16_t)strtoul(p + 10, nullptr, 10);
  } else {
    p = strstr(s, "\"on_min\":");
    if (!p) return false;
    out->on_min = (uint16_t)strtoul(p + 9, nullptr, 10);
    p = strstr(s, "\"off_min\":");
    if (!p) return false;
    out->off_min = (uint16_t)strtoul(p + 10, nullptr, 10);
  }
  p = strstr(s, "\"enabled\":");
  if (p) {
    unsigned long en = strtoul(p + 11, nullptr, 10);
    out->enabled = en ? (uint8_t)1 : (uint8_t)0;
  }
  return true;
}

static void cfSchClear(uint8_t ch) {
  if (ch >= CH_COUNT) return;
  gSchRuleCount[ch] = 0;
  memset(gSchRules[ch], 0, sizeof(gSchRules[ch]));
}

static bool cfSchWant(uint8_t ch) {
  if (ch >= CH_COUNT || gSchRuleCount[ch] == 0) return false;
  RTCTime t;
  if (!RTC.getTime(t)) return false;
  const uint8_t dowb = cfRtcDowToUiMask(t.getDayOfWeek());
  const int nowMin = t.getHour() * 60 + t.getMinutes();
  const uint32_t secDay =
    (uint32_t)t.getHour() * 3600u + (uint32_t)t.getMinutes() * 60u + (uint32_t)t.getSeconds();
  for (uint8_t ri = 0; ri < gSchRuleCount[ch]; ++ri) {
    const CfSchRule& r = gSchRules[ch][ri];
    if (!r.enabled) continue;
    if ((r.dow_mask & dowb) == 0) continue;
    if (r.kind == 0) {
      if (cfMinuteInWindow((uint16_t)nowMin, r.on_min, r.off_min)) return true;
    } else {
      if (r.on_min != 0 || r.off_min != 0) {
        if (!cfMinuteInWindow((uint16_t)nowMin, r.on_min, r.off_min)) continue;
      }
      if (cfCycleWantOn(r.on_sec, r.off_sec, secDay)) return true;
    }
  }
  return false;
}

static void cfApplySchedJson(const char* json) {
  if (!json || !*json) return;
  long ver = 0;
  const char* pv = strstr(json, "\"sch_ver\":");
  if (pv) ver = strtol(pv + 10, nullptr, 10);

  char chName[20];
  memset(chName, 0, sizeof(chName));
  const char* pc = strstr(json, "\"channel\":\"");
  if (!pc) return;
  pc += 11;
  const char* qc = strchr(pc, '"');
  if (!qc || (size_t)(qc - pc) >= sizeof(chName)) return;
  memcpy(chName, pc, (size_t)(qc - pc));

  int chIdx = -1;
  for (uint8_t i = 0; i < CH_COUNT; ++i) {
    if (strcmp(chName, CH_KEY[i]) == 0) {
      chIdx = (int)i;
      break;
    }
  }
  if (chIdx < 0) return;

  const char* pr = strstr(json, "\"rules\":[");
  if (!pr) return;
  pr += 9;
  while (*pr == ' ' || *pr == '\t' || *pr == '\n' || *pr == '\r') pr++;
  if (*pr == ']') {
    cfSchClear((uint8_t)chIdx);
    gSchVer[(uint8_t)chIdx] = (uint32_t)ver;
    Serial.print(F("SCHED clear "));
    Serial.println(chName);
    return;
  }

  static char ruleBuf[280];
  uint8_t n = 0;
  while (n < CF_SCH_MAX_RULES && *pr && *pr != ']') {
    if (*pr == ',') pr++;
    while (*pr == ' ' || *pr == '\t' || *pr == '\n' || *pr == '\r') pr++;
    if (*pr == ']') break;
    if (*pr != '{') {
      pr++;
      continue;
    }
    const char* end = strchr(pr, '}');
    if (!end) break;
    size_t len = (size_t)(end - pr) + 1;
    if (len >= sizeof(ruleBuf)) len = sizeof(ruleBuf) - 1;
    memcpy(ruleBuf, pr, len);
    ruleBuf[len] = '\0';
    CfSchRule rule;
    if (cfParseOneRule(ruleBuf, &rule) && rule.enabled) {
      gSchRules[(uint8_t)chIdx][n++] = rule;
    }
    pr = end + 1;
  }
  gSchRuleCount[(uint8_t)chIdx] = n;
  gSchVer[(uint8_t)chIdx] = (uint32_t)ver;
  if (n == 0) {
    cfApplyBuiltinScheduleForChannel((uint8_t)chIdx, gSchRuleCount, gSchRules, CH_COUNT);
    n = gSchRuleCount[(uint8_t)chIdx];
    if (n > 0) {
      Serial.print(F("SCHED builtin fallback "));
      Serial.print(chName);
      Serial.print(F(" n="));
      Serial.println(n);
    }
  } else {
    Serial.print(F("SCHED ok "));
    Serial.print(chName);
    Serial.print(F(" n="));
    Serial.println(n);
  }
  if (n > 0) chAuto[(uint8_t)chIdx] = true;
}

static void forceStartFromCh1() {
  // 환영 화면에서 다이얼/푸시 입력이 들어오면, 사용자가 현재 CH를 모르므로
  // 무조건 CH1부터 브라우즈 화면을 시작합니다.
  gUiMode = UI_BROWSE;
  gUiCh = UI_CH_ORDER[0];
  gPanelBrowseDirty = true;
  gLastBrowseDrawMs = 0;
  gPanelBrowseShown = false;
  gLcdWelcomeBypass = true;
}

static void panelNoteUserInput(uint32_t nowMs) {
  gPanelLastUserInputMs = nowMs;
  gPanelIdleWelcomeHold = false;
}

static void panelReturnToWelcome(uint32_t nowMs) {
  if (!gPanelReady || !gLcdWelcomed) {
    return;
  }
  if (gUiMode != UI_BROWSE || !gLcdWelcomeBypass) {
    return;
  }
  gLcdWelcomeBypass = false;
  gLcdWelcomeAtMs = nowMs;
  gLastLcdRtcMs = nowMs;
  gPanelBrowseShown = false;
  gPanelBrowseDirty = true;
  gPanelIdleWelcomeHold = true;
  panelSetBlink(0, 0, false);
  for (uint8_t r = 0; r < 4; r++) {
    gPanelLineInit[r] = false;
  }
  panelClear();
#if CF_PANEL_LINK_I2C
  delayMicroseconds(4500);
#endif
  lcdWelcomeSplashPaint();
}

static void panelBrowseIdleCheck(uint32_t nowMs) {
  if (!gPanelReady || !gLcdWelcomed) {
    return;
  }
  if (gUiMode != UI_BROWSE || !gLcdWelcomeBypass) {
    return;
  }
  if (gPanelLinkSplashUntilMs != 0 && (int32_t)(nowMs - gPanelLinkSplashUntilMs) < 0) {
    return;
  }
  if (!gPanelBrowseShown) {
    return;
  }
  if (gPanelLastUserInputMs == 0) {
    gPanelLastUserInputMs = nowMs;
    return;
  }
  if ((uint32_t)(nowMs - gPanelLastUserInputMs) >= PANEL_BROWSE_IDLE_MS) {
    panelReturnToWelcome(nowMs);
  }
}

// ---------- 패널 링크 (현장: R4↔R3 UART 권장) ----------
static void panelClear() {
  if (!gPanelReady) {
    return;
  }
#if CF_PANEL_LINK_I2C
  Wire.beginTransmission(PANEL_I2C_ADDR);
  Wire.write((uint8_t)PANEL_CMD_CLEAR);
  (void)Wire.endTransmission();
  delayMicroseconds(1200);
#elif CF_PANEL_LINK_UART
  panelUartTxPace();
  CF_PANEL_UART.println("C");
#else
  // no-op
#endif
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
#if CF_PANEL_LINK_I2C
  Wire.beginTransmission(PANEL_I2C_ADDR);
  Wire.write((uint8_t)PANEL_CMD_SET_LINE);
  Wire.write((uint8_t)row);
  Wire.write((uint8_t)20);
  for (uint8_t i = 0; i < 20; i++) {
    const char c = line20[i] ? line20[i] : ' ';
    Wire.write((uint8_t)c);
  }
  // I2C NACK 등 실패 시 캐시를 갱신하지 않음 — 다음 루프에서 MODE 행 등 재전송
  if (Wire.endTransmission() != 0) {
    return;
  }
  // 연속 SET_LINE 시 슬레이브 처리·버스 여유(2행 MODE 등 중간 행 유실 완화)
  delayMicroseconds(850);
#elif CF_PANEL_LINK_UART
  panelUartTxPace();
  CF_PANEL_UART.print("L,");
  CF_PANEL_UART.print((unsigned)row);
  CF_PANEL_UART.print(",");
  // R3는 20자 고정으로 해석(나머지는 공백)
  for (uint8_t i = 0; i < 20; i++) {
    char c = line20[i] ? line20[i] : ' ';
    if (c == '\r' || c == '\n') c = ' ';
    CF_PANEL_UART.print(c);
  }
  CF_PANEL_UART.println();
  // R3 SoftwareSerial이 한 줄 처리·버퍼 비우기 전에 다음 명령이 붙는 것을 줄임
  delayMicroseconds(4000);
#else
  // no-op
#endif
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
#if CF_PANEL_LINK_I2C
  Wire.beginTransmission(PANEL_I2C_ADDR);
  Wire.write((uint8_t)PANEL_CMD_BEEP);
  Wire.write((uint8_t)0);
  (void)Wire.endTransmission();
#elif CF_PANEL_LINK_UART
  panelUartTxPace();
  CF_PANEL_UART.println("B,0");
#else
  // no-op
#endif
}

static void panelBeepLong() {
  if (!gPanelReady) {
    return;
  }
#if CF_PANEL_LINK_I2C
  Wire.beginTransmission(PANEL_I2C_ADDR);
  Wire.write((uint8_t)PANEL_CMD_BEEP);
  Wire.write((uint8_t)1);
  (void)Wire.endTransmission();
#elif CF_PANEL_LINK_UART
  panelUartTxPace();
  CF_PANEL_UART.println("B,1");
#else
  // no-op
#endif
}

static void allOff();

// 부팅 자가점검: LED A1,A2,B1,B2 → Pump A1,A2,B1,B2 → Fan A1,A2,B1,B2 각 2초 ON→OFF
static const uint32_t BOOT_SELFTEST_STEP_MS = 2000UL;

static void bootSelfTestOneChannel(uint8_t ch, uint32_t holdMs) {
  if (ch >= CH_COUNT || CH_PIN[ch] < 0) return;
  digitalWrite(CH_PIN[ch], HIGH);
  chState[ch] = true;
  delay(holdMs);
  digitalWrite(CH_PIN[ch], LOW);
  chState[ch] = false;
}

static void bootSelfTestChannelList(const uint8_t* chList, uint8_t n, uint32_t holdMs) {
  for (uint8_t i = 0; i < n; i++) {
    bootSelfTestOneChannel(chList[i], holdMs);
  }
}

static void runBootSelfTestSequence() {
  Serial.println(F("BOOT self-test: LED A1,A2,B1,B2 -> Pump A1,A2,B1,B2 -> Fan A1,A2,B1,B2"));
  static const uint8_t kBootLeds[] = {
    CH_LED_A1, CH_LED_A2, CH_LED_B1, CH_LED_B2,
  };
  static const uint8_t kBootPumps[] = {
    CH_PUMP_A1, CH_PUMP_A2, CH_PUMP_B1, CH_PUMP_B2,
  };
  static const uint8_t kBootFans[] = {
    CH_FAN_A1, CH_FAN_A2, CH_FAN_B1, CH_FAN_B2,
  };
  bootSelfTestChannelList(kBootLeds, (uint8_t)(sizeof(kBootLeds) / sizeof(kBootLeds[0])), BOOT_SELFTEST_STEP_MS);
  bootSelfTestChannelList(kBootPumps, (uint8_t)(sizeof(kBootPumps) / sizeof(kBootPumps[0])), BOOT_SELFTEST_STEP_MS);
  bootSelfTestChannelList(kBootFans, (uint8_t)(sizeof(kBootFans) / sizeof(kBootFans[0])), BOOT_SELFTEST_STEP_MS);
}

/** 전 채널 AUTO·패널 MAN 홀드 해제(부팅·FORCE_AUTO_ALL·스케줄 복구). */
static void forceAllChannelsAuto(const char* reason) {
  for (uint8_t i = 0; i < CH_COUNT; ++i) {
    chAuto[i] = true;
    chManual[i] = false;
    chPanelManualUntilMs[i] = 0;
    gUiLocalOverrideAtMs[i] = 0;
  }
  gPanelBrowseDirty = true;
  gPanelUiDirty = true;
  if (reason && *reason) {
    Serial.print(F("ALL AUTO: "));
    Serial.println(reason);
  }
}

static void bootApplyBuiltinSchedAndAuto() {
  cfApplyBuiltinSchedulesIfEmpty(gSchRuleCount, gSchRules, CH_COUNT);
  forceAllChannelsAuto("boot");
  gBootBuiltinSchedDone = true;
  Serial.println(F("SCHED builtin applied; all AUTO (no boot grace)"));
}
static size_t buildTelemetryPayload(char* payload, size_t cap);
static bool mqttPublishTelePayload(const char* payload);
static bool httpPostTeleIngest(const char* payload);
static void publishTelemetry();
static void handleCmdPayload(char* buf);
static void pollSerialLine();

#if CF_PANEL_LINK_I2C
// 리셋 없이 패널 링크·브라우즈 화면 재동기화(더블 푸시 또는 I2C miss 중간 복구)
static void panelSoftRecover(uint32_t nowMs, bool userRequest) {
  if (userRequest) {
    if (gPanelLastSoftRecoverMs != 0u &&
        (uint32_t)(nowMs - gPanelLastSoftRecoverMs) < PANEL_SOFT_RECOVER_COOLDOWN_MS) {
      return;
    }
    gPanelLastSoftRecoverMs = nowMs;
    beepShort();
  }
  for (uint8_t r = 0; r < 4; r++) {
    gPanelLineInit[r] = false;
  }
  gPanelBrowseDirty = true;
  gPanelBrowseShown = false;
  gPanelIdleWelcomeHold = false;
  gPanelI2cMissStreak = 0;
  Wire.end();
  delayMicroseconds(1200);
  Wire.begin();
  if (panelI2cPing(nowMs)) {
    gPanelReady = true;
    gPanelI2cLastRxMs = nowMs;
  }
  if (gLcdWelcomed && gUiMode == UI_BROWSE) {
    gLcdWelcomeBypass = true;
    lcdBrowseDraw(nowMs);
  }
}
#endif

static void panelPollEvents(uint32_t nowMs) {
#if CF_PANEL_LINK_I2C
  // I2C 이벤트 처리 로직 (현재 사용 중)
  // R3(slave) 큐: [n][t0][p0]... (최대 14이벤트 — 엔코더 밀림 시 클릭 지연·유실 완화)
  const uint8_t want = 1 + (2 * 14);
  const int got = Wire.requestFrom((int)PANEL_I2C_ADDR, (int)want);
  gPanelI2cLastReqGot = got;
  if (got <= 0 || Wire.available() <= 0) {
    // WiFi/MQTT 재연결 등으로 루프가 잠깐 막혀도 I2C를 바로 끊지 않음(다이얼 무반응 완화)
    if (gPanelReady && gPanelI2cLastRxMs != 0) {
      gPanelI2cMissStreak++;
      const uint32_t silentMs = nowMs - gPanelI2cLastRxMs;
      if (gPanelI2cMissStreak == 18u) {
        panelSoftRecover(nowMs, false);
      }
      if (gPanelI2cMissStreak >= 40u || silentMs > 6000u) {
        gPanelReady = false;
        gPanelI2cLastRxMs = 0;
        gPanelI2cMissStreak = 0;
        for (uint8_t r = 0; r < 4; r++) {
          gPanelLineInit[r] = false;
        }
        gPanelBrowseShown = false;
        gPanelBrowseDirty = true;
      }
    }
    return;
  }
  // 이벤트가 0개(n==0)여도, I2C 응답이 왔다는 것 자체로 패널 링크는 살아있다고 판단합니다.
  gPanelReady = true;
  gPanelI2cLastRxMs = nowMs;
  gPanelI2cMissStreak = 0;
  const uint8_t n = (uint8_t)Wire.read();
  uint8_t useN = (n > 14) ? 14 : n;
  // 슬레이브가 보낸 길이와 n 불일치 시 잘못 파싱되어 CH 2칸·클릭 무시처럼 보일 수 있음
  if (got >= 1) {
    const int pairBytes = got - 1;
    if (pairBytes >= 0) {
      const uint8_t maxByWire = (uint8_t)((unsigned)pairBytes / 2u);
      if (useN > maxByWire) {
        useN = maxByWire;
      }
    }
  }
  // 한 번에 CW/CCW 여러 개를 풀면 루프 1회에 채널이 연속 점프함 → 순 방향만 ±1스텝으로 합침
  int32_t encNet = 0;
  bool sawClick = false;
  for (uint8_t i = 0; i < useN; i++) {
    if (Wire.available() < 2) break;
    const uint8_t t = (uint8_t)Wire.read();
    const uint8_t p = (uint8_t)Wire.read();
    switch (t) {
      case PANEL_EVT_ENC_CW:
        gPanelLastEvtMs = nowMs;
        gPanelEvtCount++;
        encNet++;
        break;
      case PANEL_EVT_ENC_CCW:
        gPanelLastEvtMs = nowMs;
        gPanelEvtCount++;
        encNet--;
        break;
      case PANEL_EVT_CLICK:
        gPanelLastEvtMs = nowMs;
        gPanelEvtCount++;
        sawClick = true;
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
  while (Wire.available() > 0) {
    (void)Wire.read();
  }
  if (sawClick) {
    encNet = 0;
    panelNoteUserInput(nowMs);
    if (gPanelLastClickMs != 0u &&
        (uint32_t)(nowMs - gPanelLastClickMs) < PANEL_DOUBLE_CLICK_MS) {
      gPanelLastClickMs = 0;
      panelSoftRecover(nowMs, true);
      return;
    }
    gPanelLastClickMs = nowMs;
    panelHandleClick(nowMs);
  }
  // I2C만 BROWSE에서 엔코더를 넣었던 버그 → EDIT에서 다이얼이 무시되고 SET 행도 안 갱신됨
  if (encNet != 0 && (gUiMode == UI_BROWSE || gUiMode == UI_EDIT)) {
    panelNoteUserInput(nowMs);
    if (gUiMode == UI_EDIT) {
      encoderDelta(encNet > 0 ? 1 : -1);
    } else {
      const uint32_t encGapMs = 80u;
      if (gLastEncBrowseApplyMs == 0u ||
          (uint32_t)(nowMs - gLastEncBrowseApplyMs) >= encGapMs) {
        gLastEncBrowseApplyMs = nowMs;
        encoderDelta(encNet > 0 ? 1 : -1);
      }
    }
  }
#elif CF_PANEL_LINK_UART
  {
    int uartBudget = 0;
    while (CF_PANEL_UART.available() > 0 && uartBudget < 96) {
      uartBudget++;
      const char c = (char)CF_PANEL_UART.read();
    if (c == '\r') continue;
    if (c == '\n') {
      if (gPanelRxLen == 0) continue;
      gPanelRxLine[gPanelRxLen] = '\0';
      gPanelRxLen = 0;
      gPanelReady = true;

      // R3 → R4 이벤트: "E,<t>,<p>"
      int t = -1;
      int p = 0;
      if (sscanf(gPanelRxLine, "E,%d,%d", &t, &p) == 2) {
        switch ((uint8_t)t) {
          case PANEL_EVT_ENC_CW:
            gPanelLastEvtMs = nowMs;
            gPanelEvtCount++;
            panelNoteUserInput(nowMs);
            encoderDelta(+1);
            break;
          case PANEL_EVT_ENC_CCW:
            gPanelLastEvtMs = nowMs;
            gPanelEvtCount++;
            panelNoteUserInput(nowMs);
            encoderDelta(-1);
            break;
          case PANEL_EVT_CLICK:
            gPanelLastEvtMs = nowMs;
            gPanelEvtCount++;
            panelNoteUserInput(nowMs);
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
#else
  // no-op
#endif
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

static DayOfWeek dowFromYmd(int y, int m, int d) {
  // Sakamoto algorithm: 0=Sun..6=Sat
  static const int t[] = {0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4};
  int yy = y;
  if (m < 3) yy -= 1;
  int w = (yy + yy / 4 - yy / 100 + yy / 400 + t[m - 1] + d) % 7;
  switch (w) {
    case 0: return DayOfWeek::SUNDAY;
    case 1: return DayOfWeek::MONDAY;
    case 2: return DayOfWeek::TUESDAY;
    case 3: return DayOfWeek::WEDNESDAY;
    case 4: return DayOfWeek::THURSDAY;
    case 5: return DayOfWeek::FRIDAY;
    default: return DayOfWeek::SATURDAY;
  }
}

static void rtcEnsureValidOnce() {
  // RTC 무효 시 가짜 시각(09:00) 기록하지 않음 — Pi rtc_local MQTT 대기
  static bool sDid = false;
  if (sDid) return;
  sDid = true;

  RTCTime t;
  if (RTC.getTime(t)) {
    const int y = t.getYear();
    if (y >= 2024 && y <= 2099) {
      return;
    }
  }
  Serial.println(F("RTC invalid — waiting rtc_local from Pi"));
}

static void lcdRefreshRtcDateTime() {
  if (!gPanelReady) {
    return;
  }
  RTCTime t;
  if (!RTC.getTime(t)) {
    panelPrintLine(2, "RTC -- set time");
    panelPrintLine(3, "--:--:--");
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
  snprintf(lineTime, sizeof(lineTime), "%02d:%02d:%02d", h24, mi, s);
  // I2C에서 2·3행만 간헐적으로 NACK/유실되는 케이스가 있어(웰컴에서 날짜가 비는 증상),
  // 전송 실패(gPanelLineInit=false) 시 재시도합니다.
  for (uint8_t attempt = 0; attempt < 8; attempt++) {
    panelPrintLine(2, lineDate);
    panelPrintLine(3, lineTime);
    if (gPanelLineInit[2] && gPanelLineInit[3]) {
      break;
    }
    delayMicroseconds(1400);
  }
}

// 환영 4행: RTC 초당 갱신이 2·3행만 보내면 I2C 연속 전송 구간에서 1행(CronusFarm) 한 번 실패 시 끝까지 빈 줄로 남을 수 있음 → 매번 0·1행도 같이 재전송
static void lcdWelcomeSplashPaint() {
  panelPrintLine(0, "Welcome to");
#if CF_PANEL_LINK_I2C
  delayMicroseconds(900);
#endif
  panelPrintLine(1, "CronusFarm");
#if CF_PANEL_LINK_I2C
  delayMicroseconds(1200);
#endif
  lcdRefreshRtcDateTime();
#if CF_PANEL_LINK_I2C
  delayMicroseconds(2200);
  lcdRefreshRtcDateTime();
#endif
}

static void lcdWelcomeIfOk(uint32_t nowMs, bool wifiOk, bool mqttOk) {
  (void)mqttOk;
  if (!gPanelReady) {
    return;
  }
  if (gLcdWelcomed) {
    return;
  }
  if (gPanelLinkSplashUntilMs != 0 && (int32_t)(nowMs - gPanelLinkSplashUntilMs) < 0) {
    return;
  }
  if (gPanelWaitMinUntilMs != 0 && (int32_t)(nowMs - gPanelWaitMinUntilMs) < 0) {
    return;
  }
  // MQTT 없이도 패널 UI 사용 — 브로커 지연/끊김 시 엔코더·채널 화면이 막히지 않게 함
  if (!wifiOk) {
    return;
  }

  panelClear();
#if CF_PANEL_LINK_I2C
  delayMicroseconds(4500);
#endif
  lcdWelcomeSplashPaint();

  gPanelLinkSplashUntilMs = 0;
  gPanelWaitMinUntilMs = 0;
  gLcdWelcomed = true;
  gLcdWelcomeBypass = false;
  gLcdWelcomeAtMs = nowMs;
  gLastLcdRtcMs = nowMs;
  gPanelBrowseDirty = true;
  // 환영 직후 브라우즈는 순서상 CH1(UI_CH_ORDER[0])부터 표시
  gUiCh = UI_CH_ORDER[0];
}

// 환영(5초) 이후: 채널 순서 LED A1→…→Pump B2, 엔코더로만 이동
static void lcdBrowseDraw(uint32_t nowMs) {
  if (!gPanelReady || !gLcdWelcomed) {
    return;
  }
  if (gUiMode != UI_BROWSE) {
    return;
  }
  // R3 재부팅 후 재링크: 스플래시 구간은 브라우즈가 덮지 않음(이미 환영된 세션)
  if (gPanelLinkSplashUntilMs != 0) {
    if ((int32_t)(nowMs - gPanelLinkSplashUntilMs) < 0) {
      return;
    }
    gPanelLinkSplashUntilMs = 0;
    gPanelBrowseDirty = true;
    for (uint8_t r = 0; r < 4; r++) {
      gPanelLineInit[r] = false;
    }
  }
  if (gPanelIdleWelcomeHold) {
    if ((nowMs - gLastLcdRtcMs) >= 1000) {
      gLastLcdRtcMs = nowMs;
      lcdWelcomeSplashPaint();
    }
    return;
  }
  if (!gLcdWelcomeBypass && (nowMs - gLcdWelcomeAtMs) < PANEL_WELCOME_MS) {
    return;
  }
  if ((uint32_t)(nowMs - gLcdWelcomeAtMs) >= (uint32_t)PANEL_WELCOME_MS) {
    if (!gLcdWelcomeBypass) {
      panelNoteUserInput(nowMs);
    }
    gLcdWelcomeBypass = true;
  }

  const uint8_t ch = gUiCh;
  const bool on = (digitalRead((uint8_t)CH_PIN[ch]) == HIGH);
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
  // 4) "Dial:Next, Push:Edit" (20자)
  snprintf(line1, sizeof(line1), "MODE:%s", isAuto ? "AUTO" : "MAN ");
  const int8_t pos = uiOrderPos(ch);
  const uint8_t orderCh = (pos < 0) ? (uint8_t)(ch + 1) : (uint8_t)(pos + 1);
  // "STATE:ON (또는 OFF) + 공백 4칸 + CHx/y" 고정 정렬
  // - ON은 2글자라 뒤를 1칸 패딩("ON ")으로 맞춥니다.
  const char* state3 = on ? "ON " : "OFF";
  snprintf(line2, sizeof(line2), "STATE:%s    CH%u/%u",
           state3, (unsigned)orderCh, (unsigned)CH_COUNT);
  // 20×4 LCD에 딱 맞는 힌트(시뮬/패널 예제와 동일 포맷, UART 잔상 시에도 구분 쉬움)
  snprintf(line3, sizeof(line3), "Dial:Next, Push:Edit");

  char pad0[21], pad1[21], pad2[21], pad3[21];
  panelPadLine20FromText(pad0, line0);
  panelPadLine20FromText(pad1, line1);
  panelPadLine20FromText(pad2, line2);
  panelPadLine20FromText(pad3, line3);

  bool periodic = (nowMs - gLastBrowseDrawMs) >= PANEL_BROWSE_REFRESH_MS;
#if CF_PANEL_LINK_UART
  // UART(SoftwareSerial)에서는 주기적 리프레시는 TX를 과도하게 늘려
  // R3→R4 이벤트 송신을 방해합니다. 브라우즈는 "입력/상태변경" 때만 갱신합니다.
  periodic = false;
#endif
  static uint8_t sPrevBrowseUiCh = 0xFF;
  // 채널 변경 시 3·4행 문자열이 동일해도 I2C 유실 후 캐시=패드로 rowDiff가 안 나와 빈 줄이 고착될 수 있음
  if (sPrevBrowseUiCh != ch) {
    for (uint8_t r = 0; r < 4; r++) {
      gPanelLineInit[r] = false;
    }
  }
  const bool rowDiff =
    !gPanelLineInit[0] || (memcmp(pad0, gPanelLineCache[0], 20) != 0) ||
    !gPanelLineInit[1] || (memcmp(pad1, gPanelLineCache[1], 20) != 0) ||
    !gPanelLineInit[2] || (memcmp(pad2, gPanelLineCache[2], 20) != 0) ||
    !gPanelLineInit[3] || (memcmp(pad3, gPanelLineCache[3], 20) != 0);

  if (!gPanelBrowseDirty && !periodic && !rowDiff) {
    return;
  }

  const bool chChanged = (sPrevBrowseUiCh != ch);
#if CF_PANEL_LINK_UART
  const bool needFullRedraw =
    !gPanelBrowseShown || chChanged || gPanelBrowseDirty;
#elif CF_PANEL_LINK_I2C
  const bool needFullRedraw =
    !gPanelBrowseShown || chChanged || gPanelBrowseDirty;
#else
  const bool needFullRedraw = !gPanelBrowseShown || chChanged;
#endif

#if CF_PANEL_LINK_I2C
  // 첫 브라우즈만 clear — 채널 바꿀 때마다 clear하면 2004에서 3행(STATE)만 비는 현장 케이스가 있음
  if (needFullRedraw && !gPanelBrowseShown) {
    panelClear();
  }
  panelSetBlink(0, 0, false);
  panelPrintLine(0, line0);
  panelPrintLine(1, line1);
  panelPrintLine(2, line2);
  panelPrintLine(3, line3);
  // NACK·슬레이브 밀림 시 3행(STATE) 등만 빈칸 → 재시도 + 마지막에 STATE 한 번 더
  for (uint8_t attempt = 0; attempt < 5u; attempt++) {
    bool anyMissing = false;
    for (uint8_t r = 0; r < 4; r++) {
      if (gPanelLineInit[r]) {
        continue;
      }
      anyMissing = true;
      const char* txt = (r == 0) ? line0 : (r == 1) ? line1 : (r == 2) ? line2 : line3;
      panelPrintLine(r, txt);
    }
    if (!anyMissing) {
      break;
    }
    delayMicroseconds(800);
  }
  delayMicroseconds(600);
  panelPrintLine(2, line2);
  sPrevBrowseUiCh = ch;
#else
  if (needFullRedraw) {
    panelSetBlink(0, 0, false);
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
#endif

  gPanelBrowseDirty = false;
  gLastBrowseDrawMs = nowMs;
  if (!gPanelBrowseShown) {
    panelNoteUserInput(nowMs);
  }
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

static void uiApplyEditSelection(uint8_t ch, uint8_t setVal) {
  // setVal: 0=OFF, 1=ON, 2=AUTO
  if (ch >= CH_COUNT || setVal > 2) {
    return;
  }
  gUiLocalOverrideAtMs[ch] = millis();

  if (setVal == 2) {
    chAuto[ch] = true;
    chPanelManualUntilMs[ch] = 0;
    const bool isPump =
      (ch == CH_PUMP_A1 || ch == CH_PUMP_A2 || ch == CH_PUMP_B1 || ch == CH_PUMP_B2 ||
       ch == CH_PUMP_C1 || ch == CH_PUMP_C2 || ch == CH_PUMP_D1 || ch == CH_PUMP_D2);
    if (isPump) {
      chPrevMs[ch] = millis();
    }
    return;
  }

  chAuto[ch] = false;
  chPanelManualUntilMs[ch] = millis() + PANEL_MANUAL_HOLD_MS;
  const bool on = (setVal == 1);
  chManual[ch] = on;
  digitalWrite(CH_PIN[ch], on ? HIGH : LOW);
  chState[ch] = on;
}

static void lcdRenderUi(uint32_t nowMs, bool wifiOk, bool mqttOk) {
  if (!gPanelReady) {
    return;
  }

  char line0[21];
  char line1[21];
  char line2[21];
  char line3[21];

  // WiFi+MQTT 연결 전 대기 화면
  if (!gLcdWelcomed) {
    if (gPanelLinkSplashUntilMs != 0 && (int32_t)(nowMs - gPanelLinkSplashUntilMs) < 0) {
      return;
    }
    if (gPanelLinkSplashUntilMs != 0 && (int32_t)(nowMs - gPanelLinkSplashUntilMs) >= 0) {
      gPanelLinkSplashUntilMs = 0;
      if (!wifiOk && gPanelWaitMinUntilMs == 0) {
        gPanelWaitMinUntilMs = nowMs + PANEL_LINK_WAIT_MIN_MS;
      }
    }
    // I2C 스플래시를 안 거친 경로(UART 등)에서도 대기 화면 최소 유지
    if (gPanelLinkSplashUntilMs == 0 && gPanelWaitMinUntilMs == 0 && !wifiOk) {
      gPanelWaitMinUntilMs = nowMs + PANEL_LINK_WAIT_MIN_MS;
    }
    snprintf(line0, sizeof(line0), "%s %s", CH_LABEL_KO[gUiCh], chPinLabel(gUiCh));
    const bool mqttLineOk = wifiOk && mqttOk;
    snprintf(line1, sizeof(line1), "%s %s", wifiOk ? "WiFi OK" : "WiFi --",
             mqttLineOk ? " MQTT OK" : " MQTT --");
    snprintf(line2, sizeof(line2), "Waiting link...");
    snprintf(line3, sizeof(line3), "");
    // 매 루프마다 UART 4줄을 쏘면 R3 SoftwareSerial RX가 포화되어 엔코더 이벤트가 거의 안 들어옵니다.
    static uint32_t sLastWaitUiMs = 0;
    static char sWait0[21], sWait1[21], sWait2[21], sWait3[21];
    const uint32_t interval = 350;
    if (sLastWaitUiMs != 0 && (uint32_t)(nowMs - sLastWaitUiMs) < interval &&
        strncmp(sWait0, line0, 20) == 0 && strncmp(sWait1, line1, 20) == 0 &&
        strncmp(sWait2, line2, 20) == 0 && strncmp(sWait3, line3, 20) == 0) {
      return;
    }
    sLastWaitUiMs = nowMs;
    strncpy(sWait0, line0, 20);
    sWait0[20] = '\0';
    strncpy(sWait1, line1, 20);
    sWait1[20] = '\0';
    strncpy(sWait2, line2, 20);
    sWait2[20] = '\0';
    strncpy(sWait3, line3, 20);
    sWait3[20] = '\0';
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
  // 3) SET:OFF/ON/AUTO — 다이얼로 바꾼 값이면 강조(UART: 블링크)
  // 4) 힌트
  snprintf(line0, sizeof(line0), "Setting Mode (EDIT)");
  snprintf(line1, sizeof(line1), "%s (%s)", CH_LABEL_KO[gUiCh], chPinLabel(gUiCh));
  const char* setStr = (gUiEditSet == 2) ? "AUTO" : (gUiEditSet == 1) ? "ON" : "OFF";
  snprintf(line2, sizeof(line2), "SET:%s", setStr);
  snprintf(line3, sizeof(line3), "Dial:Sel Push:OK");

  // EDIT는 매 갱신마다 4줄 전체를 강제 재전송(환영 시간/잔상 방지)
  // UART(SoftwareSerial)에서는 clear가 깜빡임/수신 포화(엔코더 이벤트 드랍)를 유발할 수 있어 피합니다.
#if CF_PANEL_LINK_I2C
  panelClear();
#endif
  gPanelUiDirty = false;
  panelPrintLine(0, line0);
  panelPrintLine(1, line1);
  panelPrintLine(2, line2);
  panelPrintLine(3, line3);
#if CF_PANEL_LINK_I2C
  // 브라우즈와 동일: NACK·슬레이브 밀림 시 3행(SET)만 빈칸되는 현장 케이스 완화
  for (uint8_t attempt = 0; attempt < 5u; attempt++) {
    bool anyMissing = false;
    for (uint8_t r = 0; r < 4; r++) {
      if (gPanelLineInit[r]) {
        continue;
      }
      anyMissing = true;
      const char* txt = (r == 0) ? line0 : (r == 1) ? line1 : (r == 2) ? line2 : line3;
      panelPrintLine(r, txt);
    }
    if (!anyMissing) {
      break;
    }
    delayMicroseconds(800);
  }
  delayMicroseconds(600);
  panelPrintLine(2, line2);
#endif
  // (EDIT) 글자 반전은 LCD 특성상 직접 구현이 어려워, 커서 블링크로 유사 반전 표시합니다.
  // "Setting Mode (EDIT)" 에서 'E' 위치(col=14)로 고정.
  panelSetBlink(0, 14, true);
  // SET 값이 "진입 시 상태"에서 변경되면 강조(SET:의 값 시작 col=4)
  panelSetBlink(2, 4, (gUiEditSet != gUiEditOrigSet));
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
    // 브라우즈 이동은 encoder 부호 그대로 UI 순서를 진행합니다.
    gUiCh = uiNextCh(gUiCh, d);
    // 채널이 바뀌면 항상 다시 그리기(환영 5초 안에서는 lcdBrowseDraw가 스킵되지만,
    // 5초 후 첫 갱신 시 최종 채널이 반영되도록 dirty 유지)
    if (prevCh != gUiCh) {
      gPanelBrowseDirty = true;
    }
    // 엔코더 회전 비프: beepShort() 비활성
  } else {
    // EDIT: OFF → ON → AUTO → OFF (CCW 역방향)
    const uint8_t prev = gUiEditSet;
    if (d > 0) {
      gUiEditSet = (uint8_t)((gUiEditSet + 1u) % 3u);
    } else {
      gUiEditSet = (uint8_t)((gUiEditSet + 2u) % 3u);
    }
    if (prev != gUiEditSet) {
      gPanelUiDirty = true;
    }
  }
}

static void panelHandleClick(uint32_t nowMs) {
  if (nowMs - gBtnLastMs < 120) {
    return;
  }
  gBtnLastMs = nowMs;
  panelNoteUserInput(nowMs);
  if (gUiMode == UI_BROWSE) {
    if (!gLcdWelcomed) {
      forceStartFromCh1();
      for (uint8_t r = 0; r < 4; r++) gPanelLineInit[r] = false;
      return;
    }
    // 환영 5초 안: 푸시는 환영 종료+CH1만(EDIT 아님)
    if (isInWelcomeWindow()) {
      gLcdWelcomeAtMs = millis() - PANEL_WELCOME_MS;
      forceStartFromCh1();
      for (uint8_t r = 0; r < 4; r++) gPanelLineInit[r] = false;
      return;
    }
    // 환영 시간 비교 오류로 isInWelcomeWindow가 남아 있어도 Edit는 열리게
    gLcdWelcomeBypass = true;
    // 환영 끝난 뒤: gPanelBrowseShown(I2C 유실 등)과 무관하게 Push→Edit (이전엔 false면 Edit 불가)
    gUiMode = UI_EDIT;
    if (chAuto[gUiCh]) {
      gUiEditSet = 2;
    } else {
      gUiEditSet = chManual[gUiCh] ? 1u : 0u;
    }
    gUiEditOrigSet = gUiEditSet;
    beepShort();
    gPanelUiDirty = true;
  } else {
    uiApplyEditSelection(gUiCh, gUiEditSet);
    beepLong();
    publishTelemetry();
    gUiMode = UI_BROWSE;
    gPanelBrowseDirty = true;
    gPanelUiDirty = false;
    panelSetBlink(0, 0, false);
  }
}

static void panelSetBlink(uint8_t row, uint8_t col, bool on) {
  // 레거시 UART 패널에서 커서 블링크로 "반전" 유사 효과를 냈던 자리입니다.
  // R3(I2C) 패널 구성에서는 미사용(호출돼도 no-op).
#if CF_PANEL_LINK_I2C
  (void)row;
  (void)col;
  (void)on;
  return;
#else
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
#endif
}

static uint32_t lastTelemetryMs = 0;
static const uint32_t TELEMETRY_INTERVAL_MS = 1000;

static WiFiClient net;
static MqttClient mqtt(net);
/** MQTT connect 실패 후 재시도 최소 간격(루프에서 connect 폭주·스택 부담 완화) */
static const uint32_t MQTT_RECONNECT_INTERVAL_MS = 5000;
/** 브로커 1곳만 시도 — 루프 한 바퀴가 mqtt.connect TCP 대기로 수십 초 막히지 않게 */
static const uint32_t MQTT_CONNECT_TIMEOUT_MS = 8000;
static uint32_t gNextMqttAttemptMs = 0;
static uint8_t gMqttBrokerTryIdx = 0;
static bool gMqttHadConnected = false;
static uint16_t gMqttClientIdSeq = 0;
static char gMqttClientIdBuf[40];

/** MQTT 연결 유지 시각 갱신. */
static void mqttNoteConnected(uint32_t nowMs) {
  gMqttLastConnectedMs = nowMs;
  if (gMqttBuiltinOfflineActive) {
    gMqttBuiltinOfflineActive = false;
    Serial.println(F("MQTT online — Pi SCHED_JSON 적용 대기"));
  }
}

/** Pi MQTT가 오래 끊기면 DB 스케줄 대신 펌웨어 builtin으로 동작. */
static void mqttMaybeBuiltinOfflineFallback(uint32_t nowMs) {
  if (mqtt.connected()) {
    mqttNoteConnected(nowMs);
    return;
  }
  if (!gMqttHadConnected) {
    return;
  }
  if (gMqttLastConnectedMs == 0) {
    gMqttLastConnectedMs = nowMs;
    return;
  }
  if ((uint32_t)(nowMs - gMqttLastConnectedMs) < MQTT_OFFLINE_BUILTIN_MS) {
    return;
  }
  if (gMqttBuiltinOfflineActive) {
    return;
  }
  cfApplyBuiltinSchedulesForceAll(gSchRuleCount, gSchRules, CH_COUNT);
  forceAllChannelsAuto("mqtt-offline-builtin");
  gMqttBuiltinOfflineActive = true;
  Serial.println(F("MQTT offline 5m+ — builtin schedule force"));
}

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

// ============================================================
// 출력 상태 복원(정책)
// - PUMP는 리셋/재부팅 시 항상 OFF
// - LED/FAN(및 기타 비-PUMP 채널)은 마지막 상태를 복원
// - 이후 스케줄/자동제어 로직이 계속 ON/OFF 수행
//
// 저장 포맷(EEPROM)
// - [160] magic(0xE1)
// - [161] ver(0x01)
// - [162] mask0 (ch 0..7)
// - [163] mask1 (ch 8..15)
// - [164] mask2 (ch 16..18 하위 3bit)
static const uint8_t EEPROM_OUT_MAGIC = 0xE1;
static const uint8_t EEPROM_OUT_VER = 0x01;
static const int EEPROM_ADDR_OUT_MAGIC = 160;
static const int EEPROM_ADDR_OUT_VER = 161;
static const int EEPROM_ADDR_OUT_MASK0 = 162;
static const int EEPROM_ADDR_OUT_MASK1 = 163;
static const int EEPROM_ADDR_OUT_MASK2 = 164;

static uint8_t gPersistLast0 = 0x00;
static uint8_t gPersistLast1 = 0x00;
static uint8_t gPersistLast2 = 0x00;
static uint32_t gPersistLastWriteMs = 0;

static inline bool isPumpCh(uint8_t ch) {
  return (ch == CH_PUMP_A1 || ch == CH_PUMP_A2 ||
          ch == CH_PUMP_B1 || ch == CH_PUMP_B2 ||
          ch == CH_PUMP_C1 || ch == CH_PUMP_C2 ||
          ch == CH_PUMP_D1 || ch == CH_PUMP_D2);
}

// ---------- 펌프 하드 가드 (연속 ON / 쿨다운 / 최소 OFF) — docs/cronusfarm_settings_schema.md §2.x
static const uint8_t PUMP_GUARD_CH[8] = {
  CH_PUMP_A1, CH_PUMP_A2, CH_PUMP_B1, CH_PUMP_B2,
  CH_PUMP_C1, CH_PUMP_C2, CH_PUMP_D1, CH_PUMP_D2,
};
static uint32_t pumpGuardConsecMs[8];
static uint32_t pumpGuardLastMs[8];
static uint32_t pumpMxUntilMs[8];      // 0 = 비활성, !=0 이면 이 시각까지 mx(쿨다운)
static uint32_t pumpMinOffUntilMs[8];  // 0 = 비활성, mf 대기

static const uint8_t EEPROM_GUARD_MAGIC = 0xC3;
static const uint8_t EEPROM_GUARD_VER = 0x01;
static const int EEPROM_GUARD_MAGIC_ADDR = 200;
static const int EEPROM_GUARD_VER_ADDR = 201;
static const int EEPROM_GUARD_COOL_BASE = 202;   // 8×uint16 LE
static const int EEPROM_GUARD_MINOFF_BASE = 218; // 8×uint16 LE

static uint32_t pumpGuardLastEepromMs = 0;
static bool pumpWasPinHigh[8];

static uint16_t eepromReadU16(int addr) {
  return (uint16_t)((uint16_t)EEPROM.read(addr) | ((uint16_t)EEPROM.read(addr + 1) << 8));
}
static void eepromWriteU16(int addr, uint16_t v) {
  EEPROM.write(addr, (uint8_t)(v & 0xFF));
  EEPROM.write(addr + 1, (uint8_t)((v >> 8) & 0xFF));
}

static void pumpGuardLoadFromEeprom() {
  if (EEPROM.read(EEPROM_GUARD_MAGIC_ADDR) != EEPROM_GUARD_MAGIC) return;
  if (EEPROM.read(EEPROM_GUARD_VER_ADDR) != EEPROM_GUARD_VER) return;
  const uint32_t nowMs = millis();
  for (uint8_t k = 0; k < 8; k++) {
    uint16_t cr = eepromReadU16(EEPROM_GUARD_COOL_BASE + (int)k * 2);
    uint16_t mr = eepromReadU16(EEPROM_GUARD_MINOFF_BASE + (int)k * 2);
    if (cr > 0) {
      pumpMxUntilMs[k] = nowMs + (uint32_t)cr * 1000ul;
    }
    if (mr > 0) {
      pumpMinOffUntilMs[k] = nowMs + (uint32_t)mr * 1000ul;
    }
  }
  pumpGuardLastEepromMs = nowMs;
}

static void pumpGuardPersistToEeprom(uint32_t nowMs) {
  EEPROM.write(EEPROM_GUARD_MAGIC_ADDR, EEPROM_GUARD_MAGIC);
  EEPROM.write(EEPROM_GUARD_VER_ADDR, EEPROM_GUARD_VER);
  for (uint8_t k = 0; k < 8; k++) {
    uint16_t cr = 0;
    if (pumpMxUntilMs[k] != 0 && (int32_t)(pumpMxUntilMs[k] - nowMs) > 0) {
      uint32_t rs = (pumpMxUntilMs[k] - nowMs + 999UL) / 1000UL;
      if (rs > 65535UL) rs = 65535UL;
      cr = (uint16_t)rs;
    }
    uint16_t mr = 0;
    if (pumpMinOffUntilMs[k] != 0 && (int32_t)(pumpMinOffUntilMs[k] - nowMs) > 0) {
      uint32_t rs = (pumpMinOffUntilMs[k] - nowMs + 999UL) / 1000UL;
      if (rs > 65535UL) rs = 65535UL;
      mr = (uint16_t)rs;
    }
    eepromWriteU16(EEPROM_GUARD_COOL_BASE + (int)k * 2, cr);
    eepromWriteU16(EEPROM_GUARD_MINOFF_BASE + (int)k * 2, mr);
  }
  pumpGuardLastEepromMs = nowMs;
}

/** 매 루프: 연속 ON 누적·상한 트립·mx/mf 출력 클램프 */
static void pumpGuardLoop(uint32_t nowMs) {
  for (uint8_t k = 0; k < 8; k++) {
    uint8_t ch = PUMP_GUARD_CH[k];
    if (pumpMxUntilMs[k] != 0 && (int32_t)(nowMs - pumpMxUntilMs[k]) >= 0) {
      pumpMxUntilMs[k] = 0;
    }
    if (pumpMinOffUntilMs[k] != 0 && (int32_t)(nowMs - pumpMinOffUntilMs[k]) >= 0) {
      pumpMinOffUntilMs[k] = 0;
    }

    uint32_t dt = 0;
    if (pumpGuardLastMs[k] != 0) {
      dt = nowMs - pumpGuardLastMs[k];
    }
    pumpGuardLastMs[k] = nowMs;
    if (dt > 60000UL) dt = 1000UL;

    const bool pinHigh = (CH_PIN[ch] >= 0) && (digitalRead((uint8_t)CH_PIN[ch]) == HIGH);
    if (pumpWasPinHigh[k] && !pinHigh) {
      pumpMinOffUntilMs[k] = nowMs + PUMP_GUARD_MIN_OFF_MS;
    }
    pumpWasPinHigh[k] = pinHigh;

    if (pinHigh) {
      pumpGuardConsecMs[k] += dt;
      if (pumpGuardConsecMs[k] >= PUMP_GUARD_MAX_ON_MS) {
        pumpGuardConsecMs[k] = 0;
        pumpMxUntilMs[k] = nowMs + PUMP_GUARD_COOLDOWN_MS;
        pumpMinOffUntilMs[k] = nowMs + PUMP_GUARD_MIN_OFF_MS;
        digitalWrite((uint8_t)CH_PIN[ch], LOW);
        chState[ch] = false;
        chManual[ch] = false;
        chPrevMs[ch] = nowMs;
        Serial.print(F("PUMP_GUARD max-on "));
        Serial.println(CH_KEY[ch]);
        pumpGuardPersistToEeprom(nowMs);
      }
    } else {
      pumpGuardConsecMs[k] = 0;
    }

    const bool wantOn = chState[ch];
    if (wantOn) {
      const bool mxBlock = (pumpMxUntilMs[k] != 0 && (int32_t)(pumpMxUntilMs[k] - nowMs) > 0);
      const bool mfBlock = (pumpMinOffUntilMs[k] != 0 && (int32_t)(pumpMinOffUntilMs[k] - nowMs) > 0);
      if (mxBlock || mfBlock) {
        digitalWrite((uint8_t)CH_PIN[ch], LOW);
        chState[ch] = false;
        chManual[ch] = false;
        chPrevMs[ch] = nowMs;
      }
    }
  }

  if (pumpGuardLastEepromMs == 0) {
    pumpGuardLastEepromMs = nowMs;
  } else if ((int32_t)(nowMs - pumpGuardLastEepromMs) >= 120000) {
    pumpGuardPersistToEeprom(nowMs);
  }
}

static void persistCompute(uint8_t* o0, uint8_t* o1, uint8_t* o2) {
  uint8_t m0 = 0, m1 = 0, m2 = 0;
  for (uint8_t ch = 0; ch < CH_COUNT; ch++) {
    if (isPumpCh(ch)) continue; // 펌프는 복원/저장 대상에서 제외
    const bool on = chState[ch];
    if (!on) continue;
    if (ch < 8) m0 |= (uint8_t)(1u << ch);
    else if (ch < 16) m1 |= (uint8_t)(1u << (ch - 8));
    else m2 |= (uint8_t)(1u << (ch - 16));
  }
  *o0 = m0;
  *o1 = m1;
  *o2 = (uint8_t)(m2 & 0x07u);
}

static void persistLoadToState() {
  // 1) 기본 안전 상태: 펌프는 항상 OFF
  for (uint8_t ch = 0; ch < CH_COUNT; ch++) {
    if (!isPumpCh(ch)) continue;
    chState[ch] = false;
    chManual[ch] = false;
    digitalWrite(CH_PIN[ch], LOW);
  }

  // 2) 복원 마스크 로드(없으면 전부 OFF 유지)
  if (EEPROM.read(EEPROM_ADDR_OUT_MAGIC) != EEPROM_OUT_MAGIC) return;
  if (EEPROM.read(EEPROM_ADDR_OUT_VER) != EEPROM_OUT_VER) return;

  const uint8_t m0 = EEPROM.read(EEPROM_ADDR_OUT_MASK0);
  const uint8_t m1 = EEPROM.read(EEPROM_ADDR_OUT_MASK1);
  const uint8_t m2 = (uint8_t)(EEPROM.read(EEPROM_ADDR_OUT_MASK2) & 0x07u);

  gPersistLast0 = m0;
  gPersistLast1 = m1;
  gPersistLast2 = m2;

  for (uint8_t ch = 0; ch < CH_COUNT; ch++) {
    if (isPumpCh(ch)) continue;
    bool on = false;
    if (ch < 8) on = (m0 & (1u << ch)) != 0;
    else if (ch < 16) on = (m1 & (1u << (ch - 8))) != 0;
    else on = (m2 & (1u << (ch - 16))) != 0;

    // LED/FAN은 기본이 수동 채널이라 chManual도 같이 맞춰 UI/tele가 일관되게 유지되도록 합니다.
    if (!chAuto[ch]) {
      chManual[ch] = on;
    }
    chState[ch] = on;
    digitalWrite(CH_PIN[ch], on ? HIGH : LOW);
  }
}

static void persistMaybeWrite(uint32_t nowMs) {
  // 너무 잦은 EEPROM write 방지
  // - 정책: 1시간 간격이면 충분(EEPROM 수명/불필요한 쓰기 감소)
  // - 마지막 기록 이후 1시간 이내에는 재기록하지 않습니다.
  if ((int32_t)(nowMs - gPersistLastWriteMs) < (int32_t)3600000) return;

  uint8_t m0, m1, m2;
  persistCompute(&m0, &m1, &m2);
  if (m0 == gPersistLast0 && m1 == gPersistLast1 && m2 == gPersistLast2) return;

  EEPROM.write(EEPROM_ADDR_OUT_MAGIC, EEPROM_OUT_MAGIC);
  EEPROM.write(EEPROM_ADDR_OUT_VER, EEPROM_OUT_VER);
  EEPROM.write(EEPROM_ADDR_OUT_MASK0, m0);
  EEPROM.write(EEPROM_ADDR_OUT_MASK1, m1);
  EEPROM.write(EEPROM_ADDR_OUT_MASK2, m2);

  gPersistLast0 = m0;
  gPersistLast1 = m1;
  gPersistLast2 = m2;
  gPersistLastWriteMs = nowMs;
}

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
    digitalWrite(CH_PIN[i], LOW);
    chState[i] = false;
  }
}

/** tele 버퍼에 안전 추가: 잘림 시 off를 cap-1로 고정(vsnprintf 반환값만 더하면 off>cap → rem 언더플로로 이후 전부 깨짐). */
static size_t tele_append_v(char* buf, size_t cap, size_t off, const char* fmt, ...) {
  if (cap == 0) return 0;
  if (off >= cap) return cap - 1;
  size_t rem = cap - off;
  if (rem <= 1) {
    buf[cap - 1] = '\0';
    return cap - 1;
  }
  va_list ap;
  va_start(ap, fmt);
  int n = vsnprintf(buf + off, rem, fmt, ap);
  va_end(ap);
  if (n < 0) return off;
  if ((size_t)n >= rem) {
    buf[cap - 1] = '\0';
    return cap - 1;
  }
  return off + (size_t)n;
}

/** tele `G:` 구간 — 비정상 펌프만 나열, 전부 정상이면 `G:ok` */
static size_t pumpGuardAppendTele(char* buf, size_t cap, size_t off, uint32_t nowMs) {
  bool anyAbnormal = false;
  char tmp[640];
  tmp[0] = '\0';
  size_t cl = 0;
  for (uint8_t k = 0; k < 8; k++) {
    const bool mxOn = (pumpMxUntilMs[k] != 0 && (int32_t)(pumpMxUntilMs[k] - nowMs) > 0);
    const bool mfOn =
      !mxOn && (pumpMinOffUntilMs[k] != 0 && (int32_t)(pumpMinOffUntilMs[k] - nowMs) > 0);
    if (mxOn) {
      uint32_t rem = (pumpMxUntilMs[k] - nowMs + 999UL) / 1000UL;
      int n = snprintf(tmp + cl, sizeof(tmp) - cl, "%s%s=mx/%lu", (cl > 0) ? " " : "",
                       CH_KEY[PUMP_GUARD_CH[k]], (unsigned long)rem);
      if (n > 0 && (size_t)n < sizeof(tmp) - cl) cl += (size_t)n;
      anyAbnormal = true;
    } else if (mfOn) {
      uint32_t rem = (pumpMinOffUntilMs[k] - nowMs + 999UL) / 1000UL;
      int n = snprintf(tmp + cl, sizeof(tmp) - cl, "%s%s=mf/%lu", (cl > 0) ? " " : "",
                       CH_KEY[PUMP_GUARD_CH[k]], (unsigned long)rem);
      if (n > 0 && (size_t)n < sizeof(tmp) - cl) cl += (size_t)n;
      anyAbnormal = true;
    }
  }
  if (!anyAbnormal) {
    return tele_append_v(buf, cap, off, " | G:ok");
  }
  return tele_append_v(buf, cap, off, " | G:%s", tmp);
}

static size_t buildTelemetryPayload(char* payload, size_t cap) {
  if (!payload || cap < 32) return 0;
  // tele: 채널 상태 + 채널별 AUTO + (펌프류) on/off
  // 예) S:led_a1=0 ... | A:led_a1=0 ... | T:pump_a1=30/90 ...
  size_t off = 0;
  off = tele_append_v(payload, cap, off, "S:");
  for (uint8_t i = 0; i < CH_COUNT; i++) {
    int v = (digitalRead(CH_PIN[i]) == HIGH) ? 1 : 0;
    off = tele_append_v(payload, cap, off, "%s=%d%s", CH_KEY[i], v, (i + 1 < CH_COUNT) ? " " : "");
    if (off >= cap - 1) break;
  }
  off = tele_append_v(payload, cap, off, " | A:");
  for (uint8_t i = 0; i < CH_COUNT; i++) {
    off = tele_append_v(payload, cap, off, "%s=%d%s", CH_KEY[i], chAuto[i] ? 1 : 0, (i + 1 < CH_COUNT) ? " " : "");
    if (off >= cap - 1) break;
  }
  off = tele_append_v(payload, cap, off, " | T:");
  bool firstT = true;
  for (uint8_t i = 0; i < CH_COUNT; i++) {
    const bool isPump =
      (i == CH_PUMP_A1 || i == CH_PUMP_A2 ||
       i == CH_PUMP_B1 || i == CH_PUMP_B2 ||
       i == CH_PUMP_C1 || i == CH_PUMP_C2 ||
       i == CH_PUMP_D1 || i == CH_PUMP_D2);
    if (!isPump) continue;
    long onSec = (long)(chOnMs[i] / 1000);
    long offSec = (long)(chOffMs[i] / 1000);
    off = tele_append_v(payload, cap, off, "%s%s=%ld/%ld", firstT ? "" : " ", CH_KEY[i], onSec, offSec);
    firstT = false;
    if (off >= cap - 1) break;
  }
  // tele에 아두이노 WiFi SSID·IP 포함(Node-RED tele raw / 구독자 확인용).
  if (off < cap - 1) {
    off = tele_append_v(payload, cap, off, " | W:");
    if (WiFi.status() == WL_CONNECTED) {
      String ss = WiFi.SSID();
      IPAddress lip = WiFi.localIP();
      off = tele_append_v(payload, cap, off, "ssid=%s ip=%u.%u.%u.%u", ss.c_str(),
                          (unsigned)lip[0], (unsigned)lip[1], (unsigned)lip[2], (unsigned)lip[3]);
    } else {
      off = tele_append_v(payload, cap, off, "ssid= ip=0.0.0.0");
    }
  }
  if (off < cap - 1) {
    RTCTime rt;
    if (RTC.getTime(rt)) {
      const int y = rt.getYear();
      const int mo = Month2int(rt.getMonth());
      const int day = rt.getDayOfMonth();
      const int h24 = rt.getHour();
      const int mi = rt.getMinutes();
      const int s = rt.getSeconds();
      if (y >= 2024 && y <= 2099) {
        off = tele_append_v(payload, cap, off,
                            " | R:%04d%02d%02d%02d%02d%02d",
                            y, mo, day, h24, mi, s);
      }
    }
  }
  // 패널(I2C) 링크 진단: 배선/주소 문제로 LCD가 갱신 안 될 때 원인 파악용
  if (off < cap - 1) {
#if CF_PANEL_LINK_I2C
    const uint32_t nowMs = millis();
    const uint32_t rxAge = (gPanelI2cLastRxMs > 0) ? (uint32_t)((nowMs - gPanelI2cLastRxMs) / 1000) : 9999;
    const uint32_t evtAge = (gPanelLastEvtMs > 0) ? (uint32_t)((nowMs - gPanelLastEvtMs) / 1000) : 9999;
    off = tele_append_v(payload, cap, off,
                        " | P:i2c_rc=%u got=%d rxage=%lus evt=%lu eage=%lus ready=%d",
                        (unsigned)gPanelI2cLastEndTxRc, (int)gPanelI2cLastReqGot,
                        (unsigned long)rxAge, (unsigned long)gPanelEvtCount,
                        (unsigned long)evtAge, gPanelReady ? 1 : 0);
#elif CF_PANEL_LINK_UART
    const uint32_t nowMs = millis();
    const uint32_t evtAge = (gPanelLastEvtMs > 0) ? (uint32_t)((nowMs - gPanelLastEvtMs) / 1000) : 9999;
    off = tele_append_v(payload, cap, off, " | P:evt=%lu age=%lus",
                        (unsigned long)gPanelEvtCount, (unsigned long)evtAge);
#endif
    off = pumpGuardAppendTele(payload, cap, off, millis());
  }
  if (off >= cap) off = cap - 1;
  payload[off] = '\0';
  return off;
}

static bool mqttPublishTelePayload(const char* payload) {
  if (!payload || !*payload || !mqtt.connected()) return false;
  mqtt.beginMessage(topicTele);
  mqtt.print(payload);
  return (mqtt.endMessage() == 0);
}

#if CRONUS_HTTP_TELE_BACKUP
static size_t jsonAppendEscaped(char* dst, size_t cap, size_t off, const char* src) {
  if (!dst || !src || off >= cap) return off;
  for (; *src && off < cap - 1; src++) {
    const char c = *src;
    if (c == '"' || c == '\\') {
      if (off + 2 >= cap) break;
      dst[off++] = '\\';
      dst[off++] = c;
    } else if (c != '\r' && c != '\n') {
      dst[off++] = c;
    }
  }
  dst[off] = '\0';
  return off;
}

static bool httpReadStatusOk(WiFiClient& client, uint32_t deadlineMs) {
  char line[20] = {0};
  uint8_t idx = 0;
  while (millis() < deadlineMs) {
    if (!client.available()) {
      if (!client.connected()) break;
      continue;
    }
    const char c = (char)client.read();
    if (c == '\r') continue;
    if (c == '\n') {
      line[sizeof(line) - 1] = '\0';
      return (strstr(line, "204") != nullptr || strstr(line, "200") != nullptr);
    }
    if (idx < sizeof(line) - 1) line[idx++] = c;
  }
  return false;
}

static bool httpPostTeleIngest(const char* teleRaw) {
  if (!teleRaw || !*teleRaw || WiFi.status() != WL_CONNECTED) return false;
  static char body[CRONUS_TELE_PAYLOAD_MAX + 220];
  size_t off = snprintf(body, sizeof(body),
                        "{\"device_id\":\"%s\",\"topic\":\"%s\",\"raw\":\"",
                        DEVICE_ID, topicTele);
  if (off >= sizeof(body) - 8) return false;
  off = jsonAppendEscaped(body, sizeof(body), off, teleRaw);
  if (off + 4 >= sizeof(body)) return false;
  body[off++] = '"';
  body[off++] = '}';
  body[off] = '\0';

  WiFiClient client;
  if (!client.connect(BRIDGE_HTTP_HOST, (uint16_t)BRIDGE_HTTP_PORT)) return false;
  client.print(F("POST "));
  client.print(BRIDGE_HTTP_PATH);
  client.print(F(" HTTP/1.1\r\nHost: "));
  client.print(BRIDGE_HTTP_HOST);
  client.print(F("\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: "));
  client.print((unsigned)off);
  client.print(F("\r\n\r\n"));
  client.print(body);
  const bool ok = httpReadStatusOk(client, millis() + 4000UL);
  client.stop();
  return ok;
}
#else
static bool httpPostTeleIngest(const char* /*teleRaw*/) { return false; }
#endif

static void serialPublishStatus(const char* st) {
  if (!st || !*st) return;
  Serial.print(F("CF_STATUS "));
  Serial.println(st);
}

static void publishTelemetry() {
  static char payload[CRONUS_TELE_PAYLOAD_MAX];
  if (buildTelemetryPayload(payload, sizeof(payload)) == 0) return;

  bool sent = false;
#if CRONUSFARM_MQTT_ENABLE
  if (WiFi.status() == WL_CONNECTED) {
    sent = mqttPublishTelePayload(payload);
#if CRONUS_HTTP_TELE_BACKUP
    if (!sent) {
      sent = httpPostTeleIngest(payload);
      if (sent) Serial.println(F("tele→HTTP ingest"));
    }
#endif
  }
#else
  /* USB primary: tele/status는 WiFi 없이도 시리얼로 Pi에 전달 */
#if CRONUS_HTTP_TELE_BACKUP
  if (WiFi.status() == WL_CONNECTED) {
    sent = httpPostTeleIngest(payload);
    if (sent) Serial.println(F("tele→HTTP ingest"));
  }
#endif
  static bool sUsbStatusOnline = false;
  if (!sUsbStatusOnline) {
    serialPublishStatus("online");
    sUsbStatusOnline = true;
  }
#endif
  (void)sent;
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
#if CF_PANEL_LINK_I2C
    panelPollEvents(millis());
#endif
    pollSerialLine();
    delay(100);
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

static void clearWifiEepromCredentials() {
  EEPROM.write(EEPROM_ADDR_MAGIC, 0);
  EEPROM.write(EEPROM_ADDR_LEN, 0);
  for (uint8_t i = 0; i < EEPROM_MAX_SSID_LEN; i++) {
    EEPROM.write(EEPROM_ADDR_SSID + (int)i, 0);
  }
  EEPROM.write(EEPROM_ADDR_DYN_MAGIC, 0);
  EEPROM.write(EEPROM_ADDR_DYN_SSID_LEN, 0);
  EEPROM.write(EEPROM_ADDR_DYN_PASS_LEN, 0);
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
  gNextMqttAttemptMs = 0;
}

// ---------- USB 시리얼 WiFi 프로비저닝 (Pi scripts/pi-serial-wifi-provision.sh) ----------
/** Pi USB cmd(SCHED_JSON 등) — MQTT cmd와 동일 상한 */
static char gSerialLine[2048];
static uint16_t gSerialLineLen = 0;

static void printWifiStatusLine() {
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print(F("OK wifi_status connected ip="));
    Serial.println(WiFi.localIP());
  } else {
    Serial.println(F("OK wifi_status disconnected"));
  }
}

static void handleSerialWifiCommand(char* line);

static void handleSerialLineDispatch(char* line) {
  trimPayload(line);
  if (!line || !*line) return;

  if (strncmp(line, "CMD ", 4) == 0) {
    char* payload = line + 4;
    while (*payload == ' ') payload++;
    Serial.print(F("CMD 수신(usb): "));
    Serial.println(payload);
    handleCmdPayload(payload);
    Serial.println(F("OK cmd"));
    return;
  }
  if (strchr(line, '=') != nullptr) {
    Serial.print(F("CMD 수신(usb kv): "));
    Serial.println(line);
    handleCmdPayload(line);
    Serial.println(F("OK cmd"));
    return;
  }
  handleSerialWifiCommand(line);
}

static void handleSerialWifiCommand(char* line) {
  trimPayload(line);
  if (!line || !*line) return;

  if (strcmp(line, "wifi_clear") == 0) {
    clearWifiEepromCredentials();
    WiFi.disconnect();
    delay(200);
    Serial.println(F("OK wifi_clear"));
    return;
  }
  if (strcmp(line, "wifi_status") == 0) {
    printWifiStatusLine();
    return;
  }
  if (strncmp(line, "wifi_set ", 9) == 0) {
    char* payload = line + 9;
    while (*payload == ' ') payload++;
    if (!*payload) {
      Serial.println(F("ERR wifi_set empty"));
      return;
    }
    Serial.print(F("OK wifi_set applying "));
    Serial.println(payload);
    handlePiWifiSsid(payload);
    printWifiStatusLine();
    return;
  }
}

static void pollSerialLine() {
  while (Serial.available() > 0) {
    const char c = (char)Serial.read();
    if (c == '\r' || c == '\n') {
      if (gSerialLineLen > 0) {
        gSerialLine[gSerialLineLen] = '\0';
        handleSerialLineDispatch(gSerialLine);
        gSerialLineLen = 0;
      }
      continue;
    }
    if (gSerialLineLen < (sizeof(gSerialLine) - 1)) {
      gSerialLine[gSerialLineLen++] = c;
    }
  }
}

static void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  pollSerialLine();

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
  for (uint8_t i = 0; i < 20; ++i) {
    pollSerialLine();
    delay(100);
  }
}

/** 재연결 시 clientId 변경 — 브로커에 남은 동일 ID 세션과 충돌·대기 완화(토픽은 DEVICE_ID 그대로). */
static void mqttApplyClientId(bool rotateForReconnect) {
  if (rotateForReconnect) {
    gMqttClientIdSeq++;
    snprintf(gMqttClientIdBuf, sizeof(gMqttClientIdBuf), "%s-r%u", DEVICE_ID,
             (unsigned)gMqttClientIdSeq);
  } else {
    snprintf(gMqttClientIdBuf, sizeof(gMqttClientIdBuf), "%s", DEVICE_ID);
  }
  mqtt.setId(gMqttClientIdBuf);
}

static void connectMqtt() {
#if !CRONUSFARM_MQTT_ENABLE
  return;
#endif
  if (mqtt.connected()) return;
  if (WiFi.status() != WL_CONNECTED) return;

  const uint32_t now = millis();
  if (gNextMqttAttemptMs != 0 && (int32_t)(now - gNextMqttAttemptMs) < 0) {
    return;
  }

#if CF_PANEL_LINK_I2C
  panelPollEvents(now);
#endif

  // clientId 매 재연결마다 바꾸면 LWT offline(retain)이 잦음 → 5회마다만 로테이션
  static uint8_t sMqttReconnectTry = 0;
  if (gMqttHadConnected || (gNextMqttAttemptMs != 0)) {
    sMqttReconnectTry++;
  }
  const bool rotateId =
      (sMqttReconnectTry >= 5u) && (sMqttReconnectTry % 5u == 0u);
  mqtt.stop();
  net.stop();
  delay(20);

  // ArduinoMqttClient 기본 TX 버퍼는 보드별로 작음(예: 256B). tele에 S|A|T|W를 붙이면
  // 크기 초과 시 끝이 잘려 Node-RED tele raw/요약에 안 보임. publishTelemetry() 버퍼와 동일하게.
  mqtt.setTxPayloadSize(CRONUS_TELE_PAYLOAD_MAX);
  // WiFi 재연결·I2C 등으로 loop가 수 초~수십 초 막히면 기본 keepalive(60s) 안에 ping이 안 나가 끊김 → 여유 확보
  mqtt.setKeepAliveInterval(120);
  net.setTimeout(MQTT_CONNECT_TIMEOUT_MS);

  mqttApplyClientId(rotateId);
  Serial.print(F("MQTT clientId="));
  Serial.println(gMqttClientIdBuf);
  if (strlen(MQTT_USER) > 0) {
    mqtt.setUsernamePassword(MQTT_USER, MQTT_PASS);
  }

  // 무한 재시도하면 setup/loop가 막혀 매트릭스가 갱신되지 않음 → loop에서 재시도
  // 브로커 비정상 단절 시에도 status retain이 offline으로 바뀌도록 LWT 등록
  mqtt.beginWill(topicStatus, true, 1);
  mqtt.print("offline");
  mqtt.endWill();

  const uint8_t bi =
      (uint8_t)(gMqttBrokerTryIdx % (uint8_t)MQTT_BROKER_COUNT);
  gMqttBrokerTryIdx++;
  const char* host = MQTT_BROKERS[bi].host;
  const uint16_t port = MQTT_BROKERS[bi].port;
  Serial.print(F("MQTT 연결 시도 "));
  Serial.print(bi + 1);
  Serial.print(F("/"));
  Serial.print(MQTT_BROKER_COUNT);
  Serial.print(F(": "));
  Serial.print(host);
  Serial.print(F(":"));
  Serial.println(port);

  pollSerialLine();
  bool mqttOk = mqtt.connect(host, port);
  if (!mqttOk) {
    Serial.print(F("  실패: "));
    Serial.println(mqtt.connectError());
    gNextMqttAttemptMs = now + MQTT_RECONNECT_INTERVAL_MS;
#if CF_PANEL_LINK_I2C
    panelPollEvents(millis());
#endif
    return;
  }
  gNextMqttAttemptMs = 0;
  gMqttHadConnected = true;
  mqttNoteConnected(millis());

  mqtt.subscribe(topicCmd, 1);
  mqtt.subscribe(topicPiWifi, 1);
  mqtt.beginMessage(topicStatus, true, 1);
  mqtt.print("online");
  mqtt.endMessage();

  Serial.println("MQTT 연결됨/구독 완료");
#if CF_PANEL_LINK_I2C
  panelPollEvents(millis());
#endif
}

#if CF_PANEL_LINK_I2C
// MQTT 끊김 + 오래 입력 없음 → R3 이벤트 큐 고갈 복구(6초 I2C 끊김과 별개)
static void panelHealIfMqttDown(uint32_t nowMs, bool mqttOk) {
  if (mqttOk || !gPanelReady || !gLcdWelcomed) {
    return;
  }
  static uint32_t sLastHealMs = 0;
  const uint32_t evtAge =
      (gPanelLastEvtMs > 0) ? (uint32_t)(nowMs - gPanelLastEvtMs) : 60000u;
  if (evtAge < 5000u) {
    return;
  }
  if (sLastHealMs != 0u && (uint32_t)(nowMs - sLastHealMs) < 12000u) {
    return;
  }
  sLastHealMs = nowMs;
  panelSoftRecover(nowMs, false);
}
#endif

static void applySingleCharCmd(const char cmd, const char* rest) {
  // 기존 Serial 호환 명령은 더 이상 사용하지 않습니다.
  // (다채널/채널별 AUTO/주기 구조로 전환)
  (void)cmd;
  (void)rest;
}

static void applyRtcLocalDigits14(const char* value) {
  // Pi 로컬 시각(예: date +%Y%m%d%H%M%S)을 그대로 R4 RV3028에 기록 — NTP·타임존은 Pi에 맡김
  if (!value) {
    return;
  }
  size_t n = strlen(value);
  if (n != 14) {
    return;
  }
  for (size_t i = 0; i < n; i++) {
    if (value[i] < '0' || value[i] > '9') {
      return;
    }
  }
  int y = 0, mo = 0, d = 0, H = 0, M = 0, S = 0;
  if (sscanf(value, "%4d%2d%2d%2d%2d%2d", &y, &mo, &d, &H, &M, &S) != 6) {
    return;
  }
  if (y < 2024 || y > 2099 || mo < 1 || mo > 12 || d < 1 || d > 31 || H < 0 || H > 23 || M < 0 || M > 59 || S < 0 || S > 59) {
    return;
  }
  DayOfWeek dow = dowFromYmd(y, mo, d);
  struct tm tm1;
  memset(&tm1, 0, sizeof(tm1));
  tm1.tm_year = y - 1900;
  tm1.tm_mon = mo - 1;
  tm1.tm_mday = d;
  tm1.tm_hour = H;
  tm1.tm_min = M;
  tm1.tm_sec = S;
  tm1.tm_wday = (int)dow;
  RTCTime ct(tm1);
  RTC.setTime(ct);
  Serial.print(F("RTC sync rtc_local="));
  Serial.println(value);
  lcdRefreshRtcDateTime();
}

static void applyKeyValue(const char* key, const char* value) {
  if (!key || !*key || !value || !*value) return;

  auto parseBool = [](const char* v) -> bool {
    return (strcmp(v, "1") == 0 || strcasecmp(v, "on") == 0 || strcasecmp(v, "true") == 0);
  };

  if (strcmp(key, "rtc_local") == 0) {
    applyRtcLocalDigits14(value);
    return;
  }

  if (strcmp(key, "SCHED_JSON") == 0) {
    static char sSchedDec[1024];
    cfUrlDecode(value, sSchedDec, sizeof(sSchedDec));
    cfApplySchedJson(sSchedDec);
    return;
  }

  if (strcmp(key, "FORCE_AUTO_ALL") == 0 || strcmp(key, "all_auto") == 0) {
    if (parseBool(value)) {
      cfApplyBuiltinSchedulesIfEmpty(gSchRuleCount, gSchRules, CH_COUNT);
      forceAllChannelsAuto("mqtt");
    }
    return;
  }

  // 웹 설정 UI 전용: ui_led_a1=0|1|2 (0=OFF 1=ON 2=AUTO) — 패널과 동일 경로
  if (strncmp(key, "ui_", 3) == 0) {
    const char* sub = key + 3;
    long v = strtol(value, nullptr, 10);
    if (v < 0) v = 0;
    if (v > 2) v = 2;
    for (uint8_t i = 0; i < CH_COUNT; i++) {
      if (strcmp(sub, CH_KEY[i]) == 0) {
        uiApplyEditSelection(i, (uint8_t)v);
        return;
      }
    }
    return;
  }

  // 1) 채널 출력: led_a1=0/1 — 자동 모드에서는 무시(수동은 ui_/패널에서만)
  for (uint8_t i = 0; i < CH_COUNT; i++) {
    if (strcmp(key, CH_KEY[i]) == 0) {
      const uint32_t now = millis();
      if (gUiLocalOverrideAtMs[i] != 0 &&
          (int32_t)(now - gUiLocalOverrideAtMs[i]) < (int32_t)UI_LOCAL_OVERRIDE_HOLD_MS) {
        return;
      }
      if (chAuto[i]) {
        return;
      }
      const bool on = parseBool(value);
      chManual[i] = on;
      chState[i] = on;
      digitalWrite(CH_PIN[i], on ? HIGH : LOW);
      return;
    }
  }

  // 2) 채널별 AUTO: auto_led_a1=0/1 ...
  if (strncmp(key, "auto_", 5) == 0) {
    const char* sub = key + 5;
    for (uint8_t i = 0; i < CH_COUNT; i++) {
      if (strcmp(sub, CH_KEY[i]) == 0) {
        const bool on = parseBool(value);
        if (!on) {
          // 수동(MAN) 전환은 R3 패널 엔코더만. MQTT auto=0 단독은 NR/retain 오염 방지로 무시.
          return;
        }
        chAuto[i] = true;
        chPanelManualUntilMs[i] = 0;
        chManual[i] = false;
        gUiLocalOverrideAtMs[i] = 0;
        gPanelBrowseDirty = true;
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

static bool pollMqttOnce() {
  int msgSize = mqtt.parseMessage();
  if (msgSize <= 0) return false;

  String t = mqtt.messageTopic();

  char payload[2048];
  int i = 0;
  while (mqtt.available() && i < (int)sizeof(payload) - 1) {
    payload[i++] = (char)mqtt.read();
  }
  payload[i] = '\0';

  if (t == String(topicCmd)) {
    Serial.print(F("CMD 수신: "));
    Serial.println(payload);
    handleCmdPayload(payload);
    return true;
  }
  if (t == String(topicPiWifi)) {
    Serial.print(F("Pi WiFi 토픽 수신: "));
    Serial.println(payload);
    handlePiWifiSsid(payload);
    return true;
  }
  return false;
}

static void pollMqttDrain() {
  for (uint8_t n = 0; n < 64 && mqtt.connected(); ++n) {
    if (!pollMqttOnce()) break;
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
  Serial.println(F("CronusFarm setup..."));
  // 부팅 직후 적용 순서(정책)
  // 1) allOff()로 전체 OFF
  // 2) persistLoadToState()로 EEPROM과 내부 마스크 동기(복원 값은 아래 3에서 덮음)
  // 3) 모든 채널 수동·OFF 고정(초기 출력·UI·tele 일치)
  persistLoadToState();
  for (uint8_t i = 0; i < CH_COUNT; i++) {
    chManual[i] = false;
    chState[i] = false;
    digitalWrite(CH_PIN[i], LOW);
  }
  runBootSelfTestSequence();
  for (uint8_t i = 0; i < CH_COUNT; i++) {
    chState[i] = false;
    digitalWrite(CH_PIN[i], LOW);
  }
  bootApplyBuiltinSchedAndAuto();
  pumpGuardLoadFromEeprom();

#if CF_PANEL_LINK_I2C
  Wire.begin();
  gPanelReady = false;
#elif CF_PANEL_LINK_UART
  CF_PANEL_UART.begin(CF_PANEL_UART_BAUD);
  delay(2);
  gPanelReady = true; // UART 링크는 즉시 사용 가능(이벤트/명령 수신으로 유지)
#else
  gPanelReady = false;
#endif

  gMatrix.begin();
  // begin 직후 한 번 그리기(MQTT 대기로 setup이 안 끝나도 이후 WiFi 성공 시 다시 갱신)
  matRenderStatus(false, false);

  gUiCh = 0;

  RTC.begin();
  rtcEnsureValidOnce();
  // RTC 무효 시 가짜 시각 기록 안 함 — Pi rtc_local·패널 표시 RTC -- 로 대기.

  buildTopics();
  connectWiFi();
  matrixShowFromPins();
#if CRONUSFARM_MQTT_ENABLE
  connectMqtt();
#endif
  matrixShowFromPins();
  publishTelemetry();
}

void loop() {
  uint32_t now = millis();
  // 패널 I2C는 WiFi/MQTT 블로킹보다 먼저 폴링(연결 대기 중에도 다이얼 유지)
  panelPollEvents(now);

  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
#if CF_PANEL_LINK_I2C
    panelPollEvents(millis());
#endif
  }
#if CRONUSFARM_MQTT_ENABLE
  if (!mqtt.connected()) {
    connectMqtt();
  }
#if CF_PANEL_LINK_I2C
  panelHealIfMqttDown(now, mqtt.connected());
#endif
#endif

  pollSerialLine();

#if CF_PANEL_LINK_I2C
  // I2C 슬레이브(R3)가 살아있으면, 이벤트가 0개여도 LCD를 R4가 소유하도록 전환합니다.
  // (그렇지 않으면 R3의 부팅/환영 화면이 계속 남아 있어 “멈춘 것처럼” 보입니다.)
  if (!gPanelReady) {
    if (panelI2cPing(now)) {
      gPanelReady = true;
      gPanelI2cLastRxMs = now;
      gPanelI2cMissStreak = 0;
      for (uint8_t r = 0; r < 4; r++) gPanelLineInit[r] = false;
      gPanelLinkSplashUntilMs = now + PANEL_LINK_SPLASH_MIN_MS;
      gPanelWaitMinUntilMs = 0;
      // 즉시 한 번 그려서 배선/통신 여부를 눈으로 확인(이후 PANEL_LINK_SPLASH_MIN_MS 동안 덮어쓰지 않음)
      const bool wifiOk = (WiFi.status() == WL_CONNECTED);
      const bool mqttLineOk = wifiOk && mqtt.connected();
      panelPrintLine(0, "CronusFarm");
      panelPrintLine(1, wifiOk ? "WiFi OK" : "WiFi --");
      panelPrintLine(2, mqttLineOk ? "MQTT OK" : "MQTT --");
      panelPrintLine(3, "Dial/Push Ready");
    }
  }
#endif
  if (!gBootBuiltinSchedDone) {
    bootApplyBuiltinSchedAndAuto();
  }
#if CRONUSFARM_MQTT_ENABLE
  mqttMaybeBuiltinOfflineFallback(now);
#endif
  // 패널 MAN 홀드 만료 → AUTO(스케줄) 복귀
  for (uint8_t i = 0; i < CH_COUNT; i++) {
    if (!chAuto[i] && chPanelManualUntilMs[i] != 0 &&
        (int32_t)(now - chPanelManualUntilMs[i]) >= 0) {
      chAuto[i] = true;
      chPanelManualUntilMs[i] = 0;
      chManual[i] = false;
      Serial.print(F("panel MAN 1h -> AUTO "));
      Serial.println(CH_KEY[i]);
    }
    // 패널 홀드 없이 수동으로 남은 채널(유령 MAN) — 스케줄 AUTO 복귀
    if (!chAuto[i] && chPanelManualUntilMs[i] == 0) {
      chAuto[i] = true;
      chManual[i] = false;
    }
  }
  // 채널별 AUTO/수동 처리
  // - AUTO=1 + 스케줄 있음: RTC 기준 window/cycle (Pi SCHED 또는 builtin)
  // - AUTO=1 + 스케줄 없음: builtin 보충 후 동일, 펌프만 on_/off_ 폴백
  // - MQTT 5분+ 끊김: mqttMaybeBuiltinOfflineFallback → 전 채널 builtin
  // - AUTO=0: chManual[] 값대로 출력
  for (uint8_t i = 0; i < CH_COUNT; i++) {
    const bool isPump =
      (i == CH_PUMP_A1 || i == CH_PUMP_A2 ||
       i == CH_PUMP_B1 || i == CH_PUMP_B2 ||
       i == CH_PUMP_C1 || i == CH_PUMP_C2 ||
       i == CH_PUMP_D1 || i == CH_PUMP_D2);
    const bool isFan = (i == CH_FAN_A1 || i == CH_FAN_A2 || i == CH_FAN_B1 || i == CH_FAN_B2);

    if (!chAuto[i]) {
      digitalWrite(CH_PIN[i], chManual[i] ? HIGH : LOW);
      chState[i] = chManual[i];
      continue;
    }

    if (gSchRuleCount[i] == 0) {
      cfApplyBuiltinScheduleForChannel(i, gSchRuleCount, gSchRules, CH_COUNT);
    }

    if (!isPump && !isFan) {
      if (gSchRuleCount[i] > 0) {
        const bool want = cfSchWant(i);
        digitalWrite(CH_PIN[i], want ? HIGH : LOW);
        chState[i] = want;
      } else {
        digitalWrite(CH_PIN[i], LOW);
        chState[i] = false;
      }
      continue;
    }

    if (isFan) {
      if (gSchRuleCount[i] > 0) {
        const bool want = cfSchWant(i);
        digitalWrite(CH_PIN[i], want ? HIGH : LOW);
        chState[i] = want;
      } else {
        digitalWrite(CH_PIN[i], LOW);
        chState[i] = false;
      }
      continue;
    }

    if (gSchRuleCount[i] > 0) {
      const bool want = cfSchWant(i);
      digitalWrite(CH_PIN[i], want ? HIGH : LOW);
      chState[i] = want;
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

  pumpGuardLoop(now);

#if CRONUSFARM_MQTT_ENABLE
  // MQTT cmd는 출력·AUTO 확정 후 처리(NR auto=0이 스케줄 루프보다 먼저 먹지 않게)
  pollMqttDrain();
#endif

  // 출력 상태 저장(정책): 펌프는 제외, 나머지 채널은 마지막 상태를 R4 EEPROM에 기록
  persistMaybeWrite(now);

  if (now - lastTelemetryMs >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryMs = now;
    publishTelemetry();
  }

#if !CRONUSFARM_MQTT_ENABLE
  static uint32_t sUsbHeartbeatMs = 0;
  if (now - sUsbHeartbeatMs >= 30000u) {
    sUsbHeartbeatMs = now;
    Serial.println(F("CF_HEARTBEAT usb"));
  }
#endif

  bool wifiOk = (WiFi.status() == WL_CONNECTED);
#if CRONUSFARM_MQTT_ENABLE
  bool mqttOk = mqtt.connected();
#else
  bool mqttOk = wifiOk;
#endif
  matrixTick(now, wifiOk, mqttOk);

  // 패널: WiFi+MQTT 후 환영(5초)→채널 브라우즈 / 다이얼=채널·편집·비프
  lcdWelcomeIfOk(now, wifiOk, mqttOk);
  if (gLcdWelcomed && gUiMode == UI_BROWSE && !gLcdWelcomeBypass &&
      (now - gLcdWelcomeAtMs) < PANEL_WELCOME_MS) {
    if (now - gLastLcdRtcMs >= 1000) {
      gLastLcdRtcMs = now;
      lcdWelcomeSplashPaint();
    }
  }
  if (gUiMode == UI_EDIT) {
    lcdRenderUi(now, wifiOk, mqttOk);
  } else if (!gLcdWelcomed) {
    lcdRenderUi(now, wifiOk, mqttOk);
  } else {
    lcdBrowseDraw(now);
    panelBrowseIdleCheck(now);
  }

#if CF_PANEL_LINK_I2C
  // LCD SET_LINE 연속 전송 직후 쌓인 클릭/엔코더를 같은 틱에서 한 번 더 수집
  panelPollEvents(millis());
#endif
}

