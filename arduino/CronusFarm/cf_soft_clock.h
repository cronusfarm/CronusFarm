#pragma once

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

/** Pi 동기 소프트웨어 시계(KST wall). RV3028/내장 RTC 미사용. */

bool cfSoftClockValid(void);
void cfSoftClockReset(void);
/** YYYYMMDDHHmmss (14자리, Pi 로컬) */
bool cfSoftClockSetLocal14(const char* digits14);
void cfSoftClockTick(uint32_t nowMillis);

uint16_t cfSoftClockYear(void);
uint8_t cfSoftClockMonth(void);
uint8_t cfSoftClockDay(void);
uint8_t cfSoftClockHour(void);
uint8_t cfSoftClockMinute(void);
uint8_t cfSoftClockSecond(void);
/** 1=Sun,2=Mon,…,64=Sat (스케줄 dow_mask와 동일) */
uint8_t cfSoftClockDowMask(void);
uint16_t cfSoftClockNowMin(void);
uint32_t cfSoftClockSecDay(void);

/** tele `R:YYYYMMDDHHmmss` */
bool cfSoftClockFormatR14(char* buf, size_t cap);

/** Pi 부팅 전: 마지막 동기 시각 EEPROM(165..179) — 전원 차단 후 millis로 진행 */
bool cfSoftClockLoadFromEeprom(char* digits14, size_t cap);
void cfSoftClockSaveToEeprom(void);
bool cfSoftClockIsCached(void);
void cfSoftClockSetCached(bool cached);
