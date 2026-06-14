/*
  CronusFarm Panel TEST (TriGorilla + Arduino Mega2560 + RepRapDiscount Smart Controller 2004A)

  목적
  - END STOPS 커넥터(X-/X+/Y+ 등)에 연결한 릴레이가 "실제로 어떤 MCU 핀"에 매핑되는지 빠르게 검증
  - I2C/Node-RED/R4 없이, 패널 단독으로 LCD에 현재 테스트 채널을 표시하고 해당 핀을 HIGH로 구동

  사용 방법(요약)
  - 아래 PIN_FAN_* 값(핀 번호)을 원하는 후보로 바꾼 뒤 업로드
  - LCD 4행에 "TEST A1 X- D3" 같은 문구가 4초마다 바뀜
  - 표시된 채널에 해당하는 릴레이가 켜지는지 확인
*/

#include <LiquidCrystal.h>

// ============================================================
// RepRapDiscount Smart Controller 2004A (TriGorilla/Mega2560) LCD 핀(마린/램프스 계열 기준)
static const int PIN_LCD_RS = 16;
static const int PIN_LCD_EN = 17;
static const int PIN_LCD_D4 = 23;
static const int PIN_LCD_D5 = 25;
static const int PIN_LCD_D6 = 27;
static const int PIN_LCD_D7 = 29;
static LiquidCrystal lcd(PIN_LCD_RS, PIN_LCD_EN, PIN_LCD_D4, PIN_LCD_D5, PIN_LCD_D6, PIN_LCD_D7);

// ============================================================
// 릴레이 출력(후보 핀) — 여기만 바꿔가며 테스트
// - A1 = X-
// - A2 = X+
// - B1 = Y+
// - B2 = Y-
//
// 주의: 보드 변형/배선에 따라 X+/Y+의 실제 핀은 달라질 수 있습니다.
static const int PIN_FAN_A1 = 3;   // X- (실측: D3)
static const int PIN_FAN_A2 = 2;   // X+ (후보)
static const int PIN_FAN_B1 = 15;  // Y+ (실측: D15)
static const int PIN_FAN_B2 = 14;  // Y- (실측: D14)

// 릴레이 트리거 레벨(현재: HIGH=ON)
static const int RELAY_ON = HIGH;
static const int RELAY_OFF = LOW;

static void lcdWriteText(uint8_t row, const char* s) {
  char b[21];
  for (uint8_t i = 0; i < 20; i++) b[i] = ' ';
  if (s) {
    for (uint8_t i = 0; i < 20 && s[i]; i++) b[i] = s[i];
  }
  b[20] = '\0';
  lcd.setCursor(0, row);
  lcd.print(b);
}

static void allOff() {
  digitalWrite(PIN_FAN_A1, RELAY_OFF);
  digitalWrite(PIN_FAN_A2, RELAY_OFF);
  digitalWrite(PIN_FAN_B1, RELAY_OFF);
  digitalWrite(PIN_FAN_B2, RELAY_OFF);
}

void setup() {
  pinMode(PIN_FAN_A1, OUTPUT);
  pinMode(PIN_FAN_A2, OUTPUT);
  pinMode(PIN_FAN_B1, OUTPUT);
  pinMode(PIN_FAN_B2, OUTPUT);
  allOff();

  lcd.begin(20, 4);
  lcdWriteText(0, "CronusFarm Panel TEST");
  lcdWriteText(1, "Relay pin scan");
  lcdWriteText(2, "A1/X- A2/X+ Y+/Y-");
  lcdWriteText(3, "booting...");
  delay(800);
}

void loop() {
  static uint32_t last = 0;
  static uint8_t step = 0;
  const uint32_t now = millis();
  if (now - last < 4000u) return;
  last = now;

  step = (uint8_t)((step + 1) % 4);

  allOff();

  int pin = PIN_FAN_A1;
  const char* label = "A1 X-";
  if (step == 1) {
    pin = PIN_FAN_A2;
    label = "A2 X+";
  } else if (step == 2) {
    pin = PIN_FAN_B1;
    label = "B1 Y+";
  } else if (step == 3) {
    pin = PIN_FAN_B2;
    label = "B2 Y-";
  }

  digitalWrite(pin, RELAY_ON);

  char line[21];
  snprintf(line, sizeof(line), "TEST %s D%-2d", label, pin);
  lcdWriteText(3, line);
}

