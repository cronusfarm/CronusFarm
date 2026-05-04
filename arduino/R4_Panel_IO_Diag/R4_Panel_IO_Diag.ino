/*
  UNO R4 WiFi + RepRapDiscount Smart Controller(2004A) I/O 진단 스케치

  목적
  - LCD는 정상인데(출력 OK) 부저/엔코더/클릭이 무반응일 때
    "핀맵/전원/풀업/극성" 문제를 LCD 화면에서 즉시 판별

  배선(현재 테스트 기준)
  - LCD: RS=D6, EN=D7, D4..D7 = D5,D4,D3,D2
  - 클릭(BTN_ENC) = D8
  - 부저(BEEPER)   = D9
  - 엔코더 A/B     = A0/A1
  - EXP2 전원: GND/5V 반드시 연결 권장
*/

#include <LiquidCrystal.h>

static const int PIN_LCD_RS = 6;
static const int PIN_LCD_EN = 7;
static const int PIN_LCD_D4 = 5;
static const int PIN_LCD_D5 = 4;
static const int PIN_LCD_D6 = 3;
static const int PIN_LCD_D7 = 2;

static const int PIN_CLICK  = 8;   // BTN_ENC
static const int PIN_BEEPER = 9;   // BEEPER
static const int PIN_ENC_A  = A0;  // BTN_EN1
static const int PIN_ENC_B  = A1;  // BTN_EN2

static LiquidCrystal lcd(PIN_LCD_RS, PIN_LCD_EN, PIN_LCD_D4, PIN_LCD_D5, PIN_LCD_D6, PIN_LCD_D7);

static bool prevClick = true;

static void beepOnce() {
  // tone()이 있으면 더 확실(패시브 부저/피에조 대응)
  tone(PIN_BEEPER, 2000, 80);
  delay(100);
  noTone(PIN_BEEPER);
}

static void printBoolAt(uint8_t col, uint8_t row, bool v) {
  lcd.setCursor(col, row);
  lcd.print(v ? "1" : "0");
}

void setup() {
  pinMode(PIN_BEEPER, OUTPUT);
  digitalWrite(PIN_BEEPER, LOW);

  pinMode(PIN_CLICK, INPUT_PULLUP);
  pinMode(PIN_ENC_A, INPUT_PULLUP);
  pinMode(PIN_ENC_B, INPUT_PULLUP);

  lcd.begin(20, 4);
  lcd.setCursor(0, 0);
  lcd.print("R4 Panel IO Diag");
  lcd.setCursor(0, 1);
  lcd.print("A0 A1 CLK BEEP");
  lcd.setCursor(0, 2);
  lcd.print("RAW: ");
  lcd.setCursor(0, 3);
  lcd.print("Click->Beep 2kHz");

  beepOnce();
}

void loop() {
  const bool a = (digitalRead(PIN_ENC_A) != 0);
  const bool b = (digitalRead(PIN_ENC_B) != 0);
  const bool c = (digitalRead(PIN_CLICK) != 0);

  // RAW는 풀업 입력이므로: 기본=1, 눌림/접지=0 이 정상
  lcd.setCursor(5, 2);
  lcd.print("A0=");
  printBoolAt(8, 2, a);
  lcd.setCursor(10, 2);
  lcd.print("A1=");
  printBoolAt(13, 2, b);
  lcd.setCursor(15, 2);
  lcd.print("C=");
  printBoolAt(17, 2, c);

  const bool pressed = (prevClick == true && c == false);
  prevClick = c;
  if (pressed) {
    beepOnce();
  }

  delay(50);
}

