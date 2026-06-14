#pragma once

#include <stdint.h>

#ifndef CF_SCH_MAX_RULES
#define CF_SCH_MAX_RULES 4
#endif

struct CfSchRule {
  uint8_t kind;
  uint8_t dow_mask;
  uint16_t on_min;
  uint16_t off_min;
  uint32_t on_sec;
  uint32_t off_sec;
  uint8_t enabled;
};
