#pragma once
// R4 ↔ Mega 패널: UART 텍스트 라인 프로토콜(Serial1 ↔ CF_UART_PORT)
// Mega→R4 이벤트: v=1;type=evt;t=<아래>;p=<바이트>
#define PANEL_EVT_ENC_CW 1
#define PANEL_EVT_ENC_CCW 2
#define PANEL_EVT_CLICK 3
#define PANEL_EVT_KILL 4
#define PANEL_EVT_SD 5
