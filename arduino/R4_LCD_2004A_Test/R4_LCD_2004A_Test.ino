/*
  UNO R4 WiFi + RepRapDiscount Smart Controller(2004A) LCD 테스트 스케치

  목적
  - "하얀 두 줄" 상태(전원만 들어오고 초기화 실패)인지 빠르게 판별
  - LCD 20x4 출력만 단독으로 검증 (엔코더/SD/부저는 제외)

  배선(사용자 최종 테스트 매핑 기준)
  - EXP1(3) RS  -> R4 D6
  - EXP1(4) E   -> R4 D7
  - EXP1(5) D4  -> R4 D5
  - EXP1(6) D5  -> R4 D4
  - EXP1(7) D6  -> R4 D3
  - EXP1(8) D7  -> R4 D2
  - EXP1(9) GND -> R4 GND
  - EXP1(10) 5V -> R4 5V

  중요
  - LCD의 R/W(5번 핀)은 반드시 GND에 고정(쓰기 전용)
  - Contrast(가변저항)는 화면이 보이도록 조절 필요
*/

#include <LiquidCrystal.h>

// LiquidCrystal(rs, enable, d4, d5, d6, d7)
static LiquidCrystal lcd(/*rs=*/6, /*en=*/7, /*d4=*/5, /*d5=*/4, /*d6=*/3, /*d7=*/2);

void setup() {
  lcd.begin(20, 4);

  lcd.setCursor(0, 0);
  lcd.print("CronusFarm V0.7");

  lcd.setCursor(0, 1);
  lcd.print("R4 LCD 2004A OK?");

  lcd.setCursor(0, 2);
  lcd.print("RS6 EN7 D5..D2");

  lcd.setCursor(0, 3);
  lcd.print("Upload: COM7");
}

void loop() {
  // 필요 시 여기에 깜박임/카운터 등을 추가할 수 있습니다.
}

