/** Bed·24h 스케줄·설정 화면 공통 채널 순서 */
export const CF_SCH_CHANNELS = [
  'led_a1', 'led_a2', 'pump_a1', 'pump_a2', 'fan_a1', 'fan_a2',
  'led_b1', 'led_b2', 'pump_b1', 'pump_b2', 'fan_b1', 'fan_b2',
  'pump_c1', 'pump_c2', 'pump_d1', 'pump_d2',
]

export const BEDS = [
  {
    id: 'A',
    title: 'A Bed',
    channels: [
      { key: 'led_a1', label: 'LED A1', pin: 'R4-D2', kind: 'led' },
      { key: 'led_a2', label: 'LED A2', pin: 'R4-D3', kind: 'led' },
      { key: 'pump_a1', label: 'Pump A1', pin: 'R4-D4', kind: 'pump' },
      { key: 'pump_a2', label: 'Pump A2', pin: 'R4-D5', kind: 'pump' },
      { key: 'fan_a1', label: 'Fan A1', pin: 'R4-D9', kind: 'fan' },
      { key: 'fan_a2', label: 'Fan A2', pin: 'R4-D10', kind: 'fan' },
    ],
  },
  {
    id: 'B',
    title: 'B Bed',
    channels: [
      { key: 'led_b1', label: 'LED B1', pin: 'R4-D6', kind: 'led' },
      { key: 'led_b2', label: 'LED B2', pin: 'R4-D13', kind: 'led' },
      { key: 'pump_b1', label: 'Pump B1', pin: 'R4-D7', kind: 'pump' },
      { key: 'pump_b2', label: 'Pump B2', pin: 'R4-D8', kind: 'pump' },
      { key: 'fan_b1', label: 'Fan B1', pin: 'R4-D11', kind: 'fan' },
      { key: 'fan_b2', label: 'Fan B2', pin: 'R4-D12', kind: 'fan' },
    ],
  },
  {
    id: 'C',
    title: 'C Bed',
    channels: [
      { key: 'pump_c1', label: 'Pump C1', pin: 'R4-A0', kind: 'pump' },
      { key: 'pump_c2', label: 'Pump C2', pin: 'R4-A1', kind: 'pump' },
    ],
  },
  {
    id: 'D',
    title: 'D Bed',
    channels: [
      { key: 'pump_d1', label: 'Pump D1', pin: 'R4-A2', kind: 'pump' },
      { key: 'pump_d2', label: 'Pump D2', pin: 'R4-A3', kind: 'pump' },
    ],
  },
]
