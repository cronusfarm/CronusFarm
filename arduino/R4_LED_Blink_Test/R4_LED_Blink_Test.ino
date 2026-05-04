/*
  UNO R4 WiFi — 내부 LED 점멸 전용 테스트
  - 다른 핀/I2C/MQTT 없음. 고릴라와 전기적 분리 검증용.
*/

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
}

void loop() {
  digitalWrite(LED_BUILTIN, HIGH);
  delay(500);
  digitalWrite(LED_BUILTIN, LOW);
  delay(500);
}
