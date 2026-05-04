/*
  TriGorilla(Mega2560) — RepRapDiscount 2004 LCD에 "Hello"만 표시하는 최소 테스트
  - CronusFarmPanel와 동일 LCD 배선 기준(RS/EN/D4~D7).
  - ENDSTOP(X-/X+/Y+/Y-) 릴레이 핀은 출력 LOW로 고정해 부팅 시 떠 있는 신호를 줄임.
*/

#include <LiquidCrystal.h>

static const int PIN_LCD_RS = 16;
static const int PIN_LCD_EN = 17;
static const int PIN_LCD_D4 = 23;
static const int PIN_LCD_D5 = 25;
static const int PIN_LCD_D6 = 27;
static const int PIN_LCD_D7 = 29;

static LiquidCrystal lcd(PIN_LCD_RS, PIN_LCD_EN, PIN_LCD_D4, PIN_LCD_D5, PIN_LCD_D6, PIN_LCD_D7);

void setup() {
  // CronusFarmPanel과 동일: 팬(엔드스톱) 릴레이 매핑 — 미구동 시 LOW 유지
  const int PIN_FAN_A1 = 3;
  const int PIN_FAN_A2 = 2;
  const int PIN_FAN_B1 = 15;
  const int PIN_FAN_B2 = 14;
  pinMode(PIN_FAN_A1, OUTPUT);
  pinMode(PIN_FAN_A2, OUTPUT);
  pinMode(PIN_FAN_B1, OUTPUT);
  pinMode(PIN_FAN_B2, OUTPUT);
  digitalWrite(PIN_FAN_A1, LOW);
  digitalWrite(PIN_FAN_A2, LOW);
  digitalWrite(PIN_FAN_B1, LOW);
  digitalWrite(PIN_FAN_B2, LOW);

  lcd.begin(20, 4);
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Hello");
}

void loop() {
}
