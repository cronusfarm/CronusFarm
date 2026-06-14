#include "cf_soft_clock.h"

#include <Arduino.h>
#include <EEPROM.h>
#include <stdio.h>
#include <string.h>

static const uint8_t EEPROM_TIME_MAGIC = 0xC6;
static const uint8_t EEPROM_TIME_VER = 0x01;
static const int EEPROM_TIME_MAGIC_ADDR = 165;
static const int EEPROM_TIME_VER_ADDR = 166;
static const int EEPROM_TIME_14_ADDR = 167;

static bool gValid = false;
static bool gCached = false;
static uint16_t gY = 2026;
static uint8_t gMo = 1;
static uint8_t gD = 1;
static uint8_t gH = 0;
static uint8_t gMi = 0;
static uint8_t gS = 0;
static uint8_t gDowMask = 1;
static uint32_t gLastTickMs = 0;

static const uint8_t kDaysInMonth[] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};

static bool isLeap(int y) {
  return (y % 4 == 0) && ((y % 100 != 0) || (y % 400 == 0));
}

static uint8_t daysInMonth(int y, int m) {
  if (m < 1 || m > 12) return 31;
  if (m == 2 && isLeap(y)) return 29;
  return kDaysInMonth[m - 1];
}

/** Sakamoto: 0=Sun … 6=Sat → dow_mask */
static uint8_t dowMaskFromYmd(int y, int m, int d) {
  static const int t[] = {0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4};
  int yy = y;
  if (m < 3) yy -= 1;
  int w = (yy + yy / 4 - yy / 100 + yy / 400 + t[m - 1] + d) % 7;
  static const uint8_t map[] = {1, 2, 4, 8, 16, 32, 64};
  if (w < 0 || w > 6) return 1;
  return map[w];
}

static void advanceOneSecond() {
  gS++;
  if (gS < 60) return;
  gS = 0;
  gMi++;
  if (gMi < 60) return;
  gMi = 0;
  gH++;
  if (gH < 24) return;
  gH = 0;
  gD++;
  const uint8_t dim = daysInMonth((int)gY, (int)gMo);
  if (gD <= dim) return;
  gD = 1;
  gMo++;
  if (gMo <= 12) {
    gDowMask = dowMaskFromYmd((int)gY, (int)gMo, (int)gD);
    return;
  }
  gMo = 1;
  gY++;
  gDowMask = dowMaskFromYmd((int)gY, (int)gMo, (int)gD);
}

bool cfSoftClockValid(void) {
  return gValid;
}

void cfSoftClockReset(void) {
  gValid = false;
  gCached = false;
  gLastTickMs = 0;
}

bool cfSoftClockIsCached(void) {
  return gCached;
}

void cfSoftClockSetCached(bool cached) {
  gCached = cached;
}

bool cfSoftClockLoadFromEeprom(char* digits14, size_t cap) {
  if (!digits14 || cap < 15) return false;
  if (EEPROM.read(EEPROM_TIME_MAGIC_ADDR) != EEPROM_TIME_MAGIC) return false;
  if (EEPROM.read(EEPROM_TIME_VER_ADDR) != EEPROM_TIME_VER) return false;
  for (int i = 0; i < 14; i++) {
    const char c = (char)EEPROM.read(EEPROM_TIME_14_ADDR + i);
    if (c < '0' || c > '9') return false;
    digits14[i] = c;
  }
  digits14[14] = '\0';
  if (!cfSoftClockSetLocal14(digits14)) return false;
  cfSoftClockSetCached(true);
  return true;
}

void cfSoftClockSaveToEeprom(void) {
  if (!gValid) return;
  char buf[16];
  if (!cfSoftClockFormatR14(buf, sizeof(buf))) return;
  EEPROM.write(EEPROM_TIME_MAGIC_ADDR, EEPROM_TIME_MAGIC);
  EEPROM.write(EEPROM_TIME_VER_ADDR, EEPROM_TIME_VER);
  for (int i = 0; i < 14; i++) {
    EEPROM.write(EEPROM_TIME_14_ADDR + i, (uint8_t)buf[i]);
  }
}

bool cfSoftClockSetLocal14(const char* digits14) {
  if (!digits14) return false;
  int y = 0, mo = 0, d = 0, H = 0, M = 0, S = 0;
  if (sscanf(digits14, "%4d%2d%2d%2d%2d%2d", &y, &mo, &d, &H, &M, &S) != 6) {
    return false;
  }
  if (y < 2024 || y > 2099 || mo < 1 || mo > 12 || d < 1 || d > 31 || H < 0 || H > 23 ||
      M < 0 || M > 59 || S < 0 || S > 59) {
    return false;
  }
  if (d > (int)daysInMonth(y, mo)) return false;
  gY = (uint16_t)y;
  gMo = (uint8_t)mo;
  gD = (uint8_t)d;
  gH = (uint8_t)H;
  gMi = (uint8_t)M;
  gS = (uint8_t)S;
  gDowMask = dowMaskFromYmd(y, mo, d);
  gValid = true;
  gLastTickMs = millis();
  if (!gCached) {
    cfSoftClockSaveToEeprom();
  }
  return true;
}

void cfSoftClockTick(uint32_t nowMillis) {
  if (!gValid) return;
  if (gLastTickMs == 0) {
    gLastTickMs = nowMillis;
    return;
  }
  uint32_t delta = (uint32_t)(nowMillis - gLastTickMs);
  if (delta < 1000u) return;
  const uint32_t addSec = delta / 1000u;
  gLastTickMs += addSec * 1000u;
  for (uint32_t i = 0; i < addSec; i++) {
    advanceOneSecond();
  }
}

uint16_t cfSoftClockYear(void) {
  return gY;
}
uint8_t cfSoftClockMonth(void) {
  return gMo;
}
uint8_t cfSoftClockDay(void) {
  return gD;
}
uint8_t cfSoftClockHour(void) {
  return gH;
}
uint8_t cfSoftClockMinute(void) {
  return gMi;
}
uint8_t cfSoftClockSecond(void) {
  return gS;
}
uint8_t cfSoftClockDowMask(void) {
  return gDowMask;
}
uint16_t cfSoftClockNowMin(void) {
  return (uint16_t)((uint16_t)gH * 60u + (uint16_t)gMi);
}
uint32_t cfSoftClockSecDay(void) {
  return (uint32_t)gH * 3600u + (uint32_t)gMi * 60u + (uint32_t)gS;
}

bool cfSoftClockFormatR14(char* buf, size_t cap) {
  if (!buf || cap < 15 || !gValid) return false;
  snprintf(buf, cap, "%04u%02u%02u%02u%02u%02u", (unsigned)gY, (unsigned)gMo, (unsigned)gD,
           (unsigned)gH, (unsigned)gMi, (unsigned)gS);
  return true;
}
