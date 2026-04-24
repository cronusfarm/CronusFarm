/*
  Trigorilla(ATmega2560) 출력 단자 테스트

  목적:
  - HOTBED(D8), HEATER0(D10), HEATER1(D45)을 3비트 숫자로 표현
    000 → 111 까지 1초 단위로 순환(테스트용)

  주의:
  - Trigorilla 스크류 단자는 “전력(12V) 출력”이며, 5A/11A 입력에 12V가 공급되어야 동작합니다.
  - 여기서는 5A 라인에 12V가 들어온 상태를 전제로 합니다.
*/

static const int PIN_HOTBED  = 8;  // HOTBED 제어 핀 (11A 입력 없으면 단자 출력은 안 나올 수 있음)
static const int PIN_HEATER0 = 10; // HEATER0 제어 핀
static const int PIN_HEATER1 = 45; // HEATER1 제어 핀

static void allOff() {
  digitalWrite(PIN_HOTBED, LOW);
  digitalWrite(PIN_HEATER0, LOW);
  digitalWrite(PIN_HEATER1, LOW);
}

static void show3bit(uint8_t v) {
  // 비트0=HOTBED, 비트1=HEATER0, 비트2=HEATER1
  digitalWrite(PIN_HOTBED,  (v & 0b001) ? HIGH : LOW);
  digitalWrite(PIN_HEATER0, (v & 0b010) ? HIGH : LOW);
  digitalWrite(PIN_HEATER1, (v & 0b100) ? HIGH : LOW);
}

void setup() {
  pinMode(PIN_HOTBED, OUTPUT);
  pinMode(PIN_HEATER0, OUTPUT);
  pinMode(PIN_HEATER1, OUTPUT);
  allOff();
}

void loop() {
  static uint8_t v = 0;
  show3bit(v);
  delay(1000);
  v = (uint8_t)((v + 1) & 0b111);
}

