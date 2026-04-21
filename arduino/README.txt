CronusFarm 아두이노 스케치 (2보드)
================================
- CronusFarm/          … UNO R4 WiFi 메인 (MQTT·릴레이·I2C 마스터). CronusFarm.ino
- CronusFarmPanel/     … UNO R3 패널 전용 (LCD·엔코더·I2C 슬레이브). CronusFarmPanel.ino
- secrets.h            … CronusFarm 전용. secrets.h.example 복사 후 로컬만 편집(Git 제외).

Pi 업로드: scripts/upcode.ps1 (R4), scripts/upcode-panel.ps1 (R3).
