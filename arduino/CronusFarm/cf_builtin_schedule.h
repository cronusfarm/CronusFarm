#pragma once

#include "cf_schedule_types.h"
#include <string.h>

// kind: 0=window, 1=cycle (cycle 시 on_min/off_min 이 0,0 이 아니면 해당 시간대만 주기 적용)
struct CfBuiltinRuleDef {
  uint8_t kind;
  uint8_t dow_mask;
  uint16_t on_min;
  uint16_t off_min;
  uint32_t on_sec;
  uint32_t off_sec;
};

struct CfBuiltinChannelDef {
  uint8_t ch;
  uint8_t rule_count;
  const CfBuiltinRuleDef* rules;
};

#define CF_BUILTIN_DOW_ALL 127

static const CfBuiltinRuleDef kBuiltinLedA2[] = {
  {0, CF_BUILTIN_DOW_ALL, 390, 1110, 0, 0},
};
static const CfBuiltinRuleDef kBuiltinLedA1[] = {
  {0, CF_BUILTIN_DOW_ALL, 390, 1110, 0, 0},
};
static const CfBuiltinRuleDef kBuiltinLedB1[] = {
  {0, CF_BUILTIN_DOW_ALL, 450, 1050, 0, 0},
};
static const CfBuiltinRuleDef kBuiltinLedB2[] = {
  {0, CF_BUILTIN_DOW_ALL, 450, 1050, 0, 0},
};

static const CfBuiltinRuleDef kBuiltinPumpA1[] = {
  {1, CF_BUILTIN_DOW_ALL, 0, 0, 900, 1200},
};
static const CfBuiltinRuleDef kBuiltinPumpA2[] = {
  {1, CF_BUILTIN_DOW_ALL, 540, 1020, 600, 3000},
  {1, CF_BUILTIN_DOW_ALL, 0, 540, 300, 3300},
  {1, CF_BUILTIN_DOW_ALL, 1020, 1440, 300, 3300},
};
static const CfBuiltinRuleDef kBuiltinPumpB2[] = {
  {1, CF_BUILTIN_DOW_ALL, 540, 1020, 600, 3000},
  {1, CF_BUILTIN_DOW_ALL, 0, 540, 300, 3300},
  {1, CF_BUILTIN_DOW_ALL, 1020, 1440, 300, 3300},
};
static const CfBuiltinRuleDef kBuiltinPumpB1[] = {
  {1, CF_BUILTIN_DOW_ALL, 450, 1050, 180, 420},
  {1, CF_BUILTIN_DOW_ALL, 0, 450, 60, 540},
  {1, CF_BUILTIN_DOW_ALL, 1050, 1440, 60, 540},
};
static const CfBuiltinRuleDef kBuiltinPumpC1[] = {
  {1, CF_BUILTIN_DOW_ALL, 0, 0, 60, 3540},
};
static const CfBuiltinRuleDef kBuiltinPumpC2[] = {
  {1, CF_BUILTIN_DOW_ALL, 0, 0, 60, 7140},
};
static const CfBuiltinRuleDef kBuiltinPumpD1[] = {
  {1, CF_BUILTIN_DOW_ALL, 0, 0, 60, 10740},
};
static const CfBuiltinRuleDef kBuiltinPumpD2[] = {
  {1, CF_BUILTIN_DOW_ALL, 0, 0, 60, 14340},
};

static const CfBuiltinRuleDef kBuiltinFan[] = {
  {0, CF_BUILTIN_DOW_ALL, 360, 1440, 0, 0},
};

// ch 인덱스는 CronusFarm.ino 의 Channel enum 과 동일
static const CfBuiltinChannelDef kBuiltinChannels[] = {
  {0, 1, kBuiltinLedA1},
  {1, 1, kBuiltinLedA2},
  {2, 1, kBuiltinLedB1},
  {3, 1, kBuiltinPumpA1},
  {4, 3, kBuiltinPumpA2},
  {5, 3, kBuiltinPumpB1},
  {6, 3, kBuiltinPumpB2},
  {7, 1, kBuiltinFan},
  {8, 1, kBuiltinFan},
  {9, 1, kBuiltinFan},
  {10, 1, kBuiltinFan},
  {11, 1, kBuiltinPumpC1},
  {12, 1, kBuiltinPumpC2},
  {13, 1, kBuiltinPumpD1},
  {14, 1, kBuiltinPumpD2},
  {15, 1, kBuiltinLedB2},
};

static inline void cfApplyBuiltinScheduleForChannel(
    uint8_t ch,
    uint8_t* ruleCount,
    CfSchRule rules[][CF_SCH_MAX_RULES],
    uint8_t chCount) {
  if (ch >= chCount || ruleCount[ch] > 0) return;
  const size_t nch = sizeof(kBuiltinChannels) / sizeof(kBuiltinChannels[0]);
  for (size_t ci = 0; ci < nch; ++ci) {
    const CfBuiltinChannelDef& def = kBuiltinChannels[ci];
    if (def.ch != ch) continue;
    uint8_t n = 0;
    for (uint8_t ri = 0; ri < def.rule_count && n < CF_SCH_MAX_RULES; ++ri) {
      const CfBuiltinRuleDef& src = def.rules[ri];
      CfSchRule& r = rules[def.ch][n++];
      memset(&r, 0, sizeof(r));
      r.kind = src.kind;
      r.dow_mask = src.dow_mask;
      r.on_min = src.on_min;
      r.off_min = src.off_min;
      r.on_sec = src.on_sec;
      r.off_sec = src.off_sec;
      r.enabled = 1;
    }
    ruleCount[def.ch] = n;
    return;
  }
}

static inline void cfApplyBuiltinSchedulesIfEmpty(
    uint8_t* ruleCount,
    CfSchRule rules[][CF_SCH_MAX_RULES],
    uint8_t chCount) {
  const size_t nch = sizeof(kBuiltinChannels) / sizeof(kBuiltinChannels[0]);
  for (size_t ci = 0; ci < nch; ++ci) {
    const CfBuiltinChannelDef& def = kBuiltinChannels[ci];
    if (def.ch >= chCount) continue;
    if (ruleCount[def.ch] > 0) continue;
    uint8_t n = 0;
    for (uint8_t ri = 0; ri < def.rule_count && n < CF_SCH_MAX_RULES; ++ri) {
      const CfBuiltinRuleDef& src = def.rules[ri];
      CfSchRule& r = rules[def.ch][n++];
      memset(&r, 0, sizeof(r));
      r.kind = src.kind;
      r.dow_mask = src.dow_mask;
      r.on_min = src.on_min;
      r.off_min = src.off_min;
      r.on_sec = src.on_sec;
      r.off_sec = src.off_sec;
      r.enabled = 1;
    }
    ruleCount[def.ch] = n;
  }
}

/** MQTT 장시간 끊김 등 — Pi SCHED 무시하고 전 채널 builtin으로 덮어씀. */
static inline void cfApplyBuiltinSchedulesForceAll(
    uint8_t* ruleCount,
    CfSchRule rules[][CF_SCH_MAX_RULES],
    uint8_t chCount) {
  for (uint8_t ch = 0; ch < chCount; ++ch) {
    ruleCount[ch] = 0;
    memset(rules[ch], 0, sizeof(rules[ch]));
  }
  cfApplyBuiltinSchedulesIfEmpty(ruleCount, rules, chCount);
}
