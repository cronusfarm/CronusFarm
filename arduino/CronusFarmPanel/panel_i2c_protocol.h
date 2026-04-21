#pragma once
// R4 WiFi(마스터) ↔ R3(슬레이브) RepRap 패널 — Wire 프로토콜 (양쪽 스케치에서 동일 값 유지)

// 7-bit I2C 주소 (충돌 시 한 곳만 변경)
#define PANEL_I2C_ADDR 0x38

// 마스터 → 슬레이브 (beginTransmission 페이로드)
#define PANEL_CMD_CLEAR 0x01    // 인자 없음
#define PANEL_CMD_SET_LINE 0x02 // row(0~3), len(0~20), len바이트 텍스트
#define PANEL_CMD_BEEP 0x03     // mode: 0=짧음, 1=김

// 슬레이브 → 마스터 (requestFrom 응답): [이벤트 개수 n][t0][p0][t1][p1]...
#define PANEL_EVT_ENC_CW 1
#define PANEL_EVT_ENC_CCW 2
#define PANEL_EVT_CLICK 3
#define PANEL_EVT_KILL 4   // param: 1=눌림
#define PANEL_EVT_SD 5     // param: 1=카드 있음, 0=없음
