/** 기본 스케줄 요약표 — Bed 순서(cronusfarm_schedule_defaults.py 와 동일) */

export const SCHEDULE_DEFAULTS_BEDS = [
  {
    bed: 'A Bed',
    rows: [
      { label: 'LED A1', rule: '시간대', detail: '06:30 ~ 18:30 ON · 그 외 OFF' },
      { label: 'LED A2', rule: '시간대', detail: '06:30 ~ 18:30 ON · 그 외 OFF' },
      {
        label: 'Pump A1',
        rule: '주기',
        detail: '0시부터 15분 ON / 20분 OFF 반복 (하루 종일)',
      },
      {
        label: 'Pump A2',
        rule: '주기',
        detail: '09:00~17:00 → 10분 ON / 50분 OFF · 그 외 5분 ON / 55분 OFF',
      },
      { label: 'Fan A1', rule: '시간대', detail: '06:00 ~ 24:00 ON · 그 외 OFF' },
      { label: 'Fan A2', rule: '시간대', detail: '06:00 ~ 24:00 ON · 그 외 OFF' },
    ],
  },
  {
    bed: 'B Bed',
    rows: [
      { label: 'LED B1', rule: '시간대', detail: '07:30 ~ 17:30 ON · 그 외 OFF' },
      { label: 'LED B2', rule: '시간대', detail: '07:30 ~ 17:30 ON · 그 외 OFF' },
      {
        label: 'Pump B1',
        rule: '주기',
        detail: '07:30~17:30 → 3분 ON / 7분 OFF · 그 외 1분 ON / 9분 OFF',
      },
      {
        label: 'Pump B2',
        rule: '주기',
        detail: '09:00~17:00 → 10분 ON / 50분 OFF · 그 외 5분 ON / 55분 OFF',
      },
      { label: 'Fan B1', rule: '시간대', detail: '06:00 ~ 24:00 ON · 그 외 OFF' },
      { label: 'Fan B2', rule: '시간대', detail: '06:00 ~ 24:00 ON · 그 외 OFF' },
    ],
  },
  {
    bed: 'C Bed',
    rows: [
      { label: 'Pump C1', rule: '주기', detail: '1시간 주기 · 1분 ON' },
      { label: 'Pump C2', rule: '주기', detail: '2시간 주기 · 1분 ON' },
    ],
  },
  {
    bed: 'D Bed',
    rows: [
      { label: 'Pump D1', rule: '주기', detail: '3시간 주기 · 1분 ON' },
      { label: 'Pump D2', rule: '주기', detail: '4시간 주기 · 1분 ON' },
    ],
  },
]
