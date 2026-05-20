import { BEDS } from '@/constants/channels'

const LABEL_BY_KEY = Object.create(null)
const KIND_BY_KEY = Object.create(null)
for (const bed of BEDS) {
  for (const ch of bed.channels) {
    LABEL_BY_KEY[ch.key] = ch.label
    KIND_BY_KEY[ch.key] = ch.kind
  }
}

/** 모니터 Bed 히스토리와 동일 표기 (예: pump_a1 → Pump A1) */
export function channelLabel(key) {
  return LABEL_BY_KEY[key] || key
}

export function channelKind(key) {
  return KIND_BY_KEY[key] || ''
}
