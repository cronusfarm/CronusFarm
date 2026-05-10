#include <LiquidCrystal.h>

static LiquidCrystal lcd(6, 7, 5, 4, 3, 2);

static const int PIN_CLICK = 8;
static const int PIN_ENC_A = A0;
static const int PIN_ENC_B = A1;

static int8_t gEncPrevAB = 0;
static int8_t gEncPrevA = -1;
static int8_t gEncPrevB = -1;
static int8_t gEncAccum = 0;
static uint32_t gEncLastMs = 0;
static const int8_t ENC_STEPS_PER_EVENT = 3;
static const int8_t ENC_DIR = -1; 

static uint32_t gBtnLastMs = 0;
static bool gBtnPrev = true;

enum UiMode : uint8_t { UI_WELCOME = 0, UI_BROWSE = 1, UI_EDIT = 2 };
static UiMode gUiMode = UI_WELCOME;
static uint32_t gWelcomeAtMs = 0;

static const uint8_t CH_COUNT = 19;
static const char* const CH_LABEL_KO[CH_COUNT] = {
  "LED A1",  "LED A2",  "LED B1",
  "PUMP A1", "PUMP A2", "PUMP B1", "PUMP B2",
  "PUMP C1", "PUMP C2", "PUMP D1", "PUMP D2",
  "FAN A1",  "FAN A2",  "FAN B1",  "FAN B2",
  "SERVO0",  "SERVO1",  "SERVO2",  "SERVO3",
};
static const char* const CH_PIN_LABEL[CH_COUNT] = {
  "R4-D2", "R4-D3", "R4-D6",
  "R4-D4", "R4-D5", "R4-D7", "R4-D8",
  "R4-D9", "R4-D10", "R4-D11", "R4-D12",
  "TG-D3", "TG-D2", "TG-D14", "TG-D15",
  "TG-S0", "TG-S1", "TG-S2", "TG-S3",
};

static bool gChOn[CH_COUNT] = { false };
static uint8_t gCh = 0; 
static bool gPickOn = false; 
static bool gEditOrigOn = false;

static void pad20(char out[21], const char* s) {
  for (int i = 0; i < 20; i++) out[i] = ' ';
  out[20] = '\0';
  if (!s) return;
  for (int i = 0; i < 20 && s[i]; i++) out[i] = s[i];
}

static void drawBrowse() {
  char l0[21], l1[21], l2[21], l3[21];
  {
    char tmp[64];
    snprintf(tmp, sizeof(tmp), "%s (%s)", CH_LABEL_KO[gCh], CH_PIN_LABEL[gCh]);
    pad20(l0, tmp);
  }
  pad20(l1, "MODE:MAN");
  {
    char tmp[64];
    const char* st = gChOn[gCh] ? "ON" : "OFF";
    snprintf(tmp, sizeof(tmp), "STATE:%-3s    CH%02u/%02u", st, (unsigned)(gCh + 1), (unsigned)CH_COUNT);
    pad20(l2, tmp);
  }
  pad20(l3, "Dial:Next, Push:Edit");

  lcd.clear();
  lcd.setCursor(0, 0); lcd.print(l0);
  lcd.setCursor(0, 1); lcd.print(l1);
  lcd.setCursor(0, 2); lcd.print(l2);
  lcd.setCursor(0, 3); lcd.print(l3);
}

static void drawEdit() {
  char l0[21], l1[21], l2[21], l3[21];
  pad20(l0, "Setting Mode (EDIT)");
  {
    char tmp[64];
    snprintf(tmp, sizeof(tmp), "%s (%s)", CH_LABEL_KO[gCh], CH_PIN_LABEL[gCh]);
    pad20(l1, tmp);
  }
  {
    char tmp[32];
    snprintf(tmp, sizeof(tmp), "SET:%s", gPickOn ? "ON" : "OFF");
    pad20(l2, tmp);
  }
  pad20(l3, "Dial:ON/OFF, Push:OK");

  lcd.clear();
  lcd.setCursor(0, 0); lcd.print(l0);
  lcd.setCursor(0, 1); lcd.print(l1);
  lcd.setCursor(0, 2); lcd.print(l2);
  lcd.setCursor(0, 3); lcd.print(l3);

  lcd.noBlink();
  lcd.noCursor();
  lcd.setCursor(3, 2);
  lcd.blink();
}

static void enterBrowseFromWelcome() {
  gUiMode = UI_BROWSE;
  gCh = 0;
  gPickOn = gChOn[gCh];
  drawBrowse();
}

static void onEncoderEvent(int8_t dir) {
  if (dir == 0) return;
  if (gUiMode == UI_WELCOME) {
    enterBrowseFromWelcome();
    return;
  }
  if (gUiMode == UI_BROWSE) {
    int ch = (int)gCh + (dir > 0 ? 1 : -1);
    if (ch < 0) ch = (int)CH_COUNT - 1;
    if (ch >= (int)CH_COUNT) ch = 0;
    gCh = (uint8_t)ch;
    gPickOn = gChOn[gCh];
    drawBrowse();
    return;
  }
  gPickOn = !gPickOn;
  drawEdit();
}

static void onClick() {
  const uint32_t now = millis();
  if (now - gBtnLastMs < 220) return;
  gBtnLastMs = now;

  if (gUiMode == UI_WELCOME) {
    enterBrowseFromWelcome();
    return;
  }
  if (gUiMode == UI_BROWSE) {
    gUiMode = UI_EDIT;
    gPickOn = gChOn[gCh];
    gEditOrigOn = gPickOn;
    drawEdit();
    return;
  }
  gChOn[gCh] = gPickOn;
  lcd.noBlink();
  lcd.noCursor();
  gUiMode = UI_BROWSE;
  drawBrowse();
}

static void encoderPoll() {
  uint32_t now = millis();
  if (now - gEncLastMs < 2) return;
  gEncLastMs = now;

  int a = digitalRead(PIN_ENC_A) ? 1 : 0;
  int b = digitalRead(PIN_ENC_B) ? 1 : 0;
  int8_t ab = (int8_t)((a << 1) | b);

  static const int8_t delta[16] = {
    0, +1, -1, 0,
    -1, 0, 0, +1,
    +1, 0, 0, -1,
    0, -1, +1, 0
  };
  int8_t idx = (int8_t)((gEncPrevAB << 2) | ab);
  int8_t d = (int8_t)(delta[(uint8_t)idx] * ENC_DIR);
  gEncPrevAB = ab;

  if (gEncPrevA < 0 || gEncPrevB < 0) {
    gEncPrevA = (int8_t)a;
    gEncPrevB = (int8_t)b;
    return;
  }

  if (d == 0 && (a != gEncPrevA || b != gEncPrevB)) {
    if (a != gEncPrevA) d = (int8_t)(((b == a) ? +1 : -1) * ENC_DIR);
    else d = (int8_t)(((a != b) ? +1 : -1) * ENC_DIR);
  }
  gEncPrevA = (int8_t)a;
  gEncPrevB = (int8_t)b;

  if (d == 0) return;
  gEncAccum = (int8_t)(gEncAccum + d);
  if (gEncAccum >= ENC_STEPS_PER_EVENT) {
    gEncAccum = 0;
    onEncoderEvent(+1);
  } else if (gEncAccum <= (int8_t)(-ENC_STEPS_PER_EVENT)) {
    gEncAccum = 0;
    onEncoderEvent(-1);
  }
}

static void clickPoll() {
  bool cur = digitalRead(PIN_CLICK) ? true : false;
  bool pressed = (gBtnPrev == true && cur == false);
  gBtnPrev = cur;
  if (pressed) onClick();
}

void setup() {
  pinMode(PIN_CLICK, INPUT_PULLUP);
  pinMode(PIN_ENC_A, INPUT_PULLUP);
  pinMode(PIN_ENC_B, INPUT_PULLUP);

  lcd.begin(20, 4);
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("CronusFarm Panel");
  lcd.setCursor(0, 1);
  lcd.print("V0.7 UI SIM (R4)");
  lcd.setCursor(0, 3);
  lcd.print("Dial/Push to start");
  gWelcomeAtMs = millis();
}

void loop() {
  (void)gWelcomeAtMs;
  encoderPoll();
  clickPoll();
}