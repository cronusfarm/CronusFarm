-- 아티초크 스마트팜 SQLite 스키마 (문서: smartfarm_db_schema.md 기반)
-- 주의:
-- - 이 파일은 "DB 구조 정의"입니다. Grafana 대시보드가 데이터를 보이게 하려면 별도 적재(작물/이미지/AI/알림) 파이프라인이 필요합니다.
-- - 재적용 안전을 위해 CREATE는 IF NOT EXISTS, 기본 설정값은 OR IGNORE로 넣습니다.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS zones (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  zone_code     TEXT NOT NULL UNIQUE,           -- 'zone_a', 'zone_b'
  zone_name     TEXT NOT NULL,                  -- '재배동 A구역'
  area_m2       REAL,                           -- 면적 (㎡)
  plant_rows    INTEGER,                        -- 재식 행 수
  plant_cols    INTEGER,                        -- 재식 열 수
  description   TEXT,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crops (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  zone_id         INTEGER NOT NULL REFERENCES zones(id),
  crop_code       TEXT NOT NULL,                -- 'ATC-2025-001'
  variety         TEXT NOT NULL,                -- 아티초크 품종 ('Green Globe', 'Violetto')
  plant_date      DATE NOT NULL,                -- 정식일
  expected_harvest DATE,                        -- 예상 수확일
  seed_source     TEXT,                         -- 종묘 출처
  row_pos         INTEGER,                      -- 행 위치
  col_pos         INTEGER,                      -- 열 위치
  status          TEXT DEFAULT 'growing',       -- 'seedling' / 'growing' / 'flowering' / 'harvested' / 'removed'
  notes           TEXT,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_crops_zone ON crops(zone_id);
CREATE INDEX IF NOT EXISTS idx_crops_status ON crops(status);

CREATE TABLE IF NOT EXISTS growth_stages (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  crop_id         INTEGER NOT NULL REFERENCES crops(id),
  stage           TEXT NOT NULL,                -- 'germination' / 'seedling' / 'vegetative' / 'budding' / 'flowering' / 'maturity'
  stage_order     INTEGER NOT NULL,             -- 단계 순서 (1~6)
  started_at      DATE NOT NULL,
  ended_at        DATE,
  duration_days   INTEGER,                      -- 소요 일수 (ended_at - started_at)
  height_cm       REAL,                         -- 초장 (cm)
  leaf_count      INTEGER,                      -- 엽수
  bud_count       INTEGER,                      -- 꽃봉오리 수
  health_score    REAL,                         -- 건강도 점수 (0~100, AI 평가)
  notes           TEXT,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS devices (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  device_code     TEXT NOT NULL UNIQUE,         -- 'led_1', 'pump_3', 'fan_2'
  device_type     TEXT NOT NULL,                -- 'led' / 'pump' / 'fan' / 'sensor' / 'camera'
  device_name     TEXT NOT NULL,                -- '재배동 A 주광 LED 1번'
  zone_id         INTEGER REFERENCES zones(id),
  manufacturer    TEXT,
  model           TEXT,
  serial_no       TEXT,
  install_date    DATE,
  rated_power_w   REAL,                         -- 정격 소비전력 (W)
  gpio_pin        INTEGER,                      -- Pi GPIO 핀 번호
  ip_address      TEXT,                         -- 네트워크 장치일 경우
  is_active       INTEGER DEFAULT 1,            -- 0: 비활성 / 1: 활성
  specs_json      TEXT,                         -- 추가 스펙 (JSON)
  notes           TEXT,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS operation_logs (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id       INTEGER NOT NULL REFERENCES devices(id),
  started_at      DATETIME NOT NULL,            -- ON 시각
  ended_at        DATETIME,                     -- OFF 시각 (NULL = 아직 가동 중)
  duration_sec    INTEGER,                      -- 가동 시간 (초) — ended_at 시 자동 계산
  trigger_type    TEXT NOT NULL,                -- 'manual' / 'schedule' / 'auto' / 'api'
  trigger_reason  TEXT,                         -- 'temp_high', 'schedule_id:5' 등
  operator        TEXT,                         -- 수동 조작자 (자동이면 'system')
  set_value       REAL,                         -- 설정값 (Fan: rpm, LED: 밝기%)
  notes           TEXT,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_oplog_device ON operation_logs(device_id);
CREATE INDEX IF NOT EXISTS idx_oplog_started ON operation_logs(started_at);

CREATE TABLE IF NOT EXISTS schedules (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id       INTEGER NOT NULL REFERENCES devices(id),
  schedule_name   TEXT NOT NULL,                -- '오전 점등 스케줄'
  cron_expr       TEXT NOT NULL,                -- cron 표현식 ('0 6 * * *')
  action          TEXT NOT NULL,                -- 'ON' / 'OFF' / 'SET'
  set_value       REAL,                         -- SET 시 설정값
  duration_min    INTEGER,                      -- ON 유지 시간 (분), NULL = 별도 OFF 스케줄
  is_active       INTEGER DEFAULT 1,
  valid_from      DATE,
  valid_until     DATE,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS schedule_executions (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  schedule_id     INTEGER NOT NULL REFERENCES schedules(id),
  executed_at     DATETIME NOT NULL,
  result          TEXT NOT NULL,                -- 'success' / 'failed' / 'skipped'
  error_msg       TEXT,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS images (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  camera_id       INTEGER NOT NULL REFERENCES devices(id),
  crop_id         INTEGER REFERENCES crops(id),
  zone_id         INTEGER REFERENCES zones(id),
  captured_at     DATETIME NOT NULL,            -- 촬영 시각
  file_path       TEXT NOT NULL,                -- 저장 경로 ('/data/images/2025/04/cam1_20250401_083000.jpg')
  file_size_kb    INTEGER,                      -- 파일 크기 (KB)
  resolution      TEXT,                         -- '1920x1080'
  trigger_type    TEXT NOT NULL,                -- 'schedule' / 'motion' / 'ai_event' / 'manual'
  has_ai_result   INTEGER DEFAULT 0,            -- AI 분석 완료 여부
  thumbnail_path  TEXT,                         -- 썸네일 경로
  is_archived     INTEGER DEFAULT 0,            -- 아카이브 여부
  notes           TEXT,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_images_captured ON images(captured_at);
CREATE INDEX IF NOT EXISTS idx_images_crop ON images(crop_id);
CREATE INDEX IF NOT EXISTS idx_images_ai ON images(has_ai_result);

CREATE TABLE IF NOT EXISTS ai_detections (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  image_id        INTEGER NOT NULL REFERENCES images(id),
  detected_at     DATETIME NOT NULL,
  model_name      TEXT NOT NULL,                -- 'yolov8n_artichoke_v2'
  model_version   TEXT,
  detection_type  TEXT NOT NULL,                -- 'growth_stage' / 'disease' / 'pest' / 'harvest_ready' / 'anomaly'
  label           TEXT NOT NULL,                -- 'budding' / 'aphid' / 'leaf_blight' / 'harvest_ready'
  confidence      REAL NOT NULL,                -- 신뢰도 (0.0 ~ 1.0)
  bbox_json       TEXT,                         -- 바운딩박스 JSON {"x":10,"y":20,"w":100,"h":80}
  severity        TEXT,                         -- 'low' / 'medium' / 'high' / 'critical'
  action_taken    TEXT,                         -- 실제 수행된 조치
  is_confirmed    INTEGER DEFAULT 0,            -- 사용자 확인 여부
  notes           TEXT,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_detected ON ai_detections(detected_at);
CREATE INDEX IF NOT EXISTS idx_ai_type ON ai_detections(detection_type);
CREATE INDEX IF NOT EXISTS idx_ai_severity ON ai_detections(severity);

CREATE TABLE IF NOT EXISTS alert_events (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  alert_type      TEXT NOT NULL,                -- 'sensor_out_of_range' / 'device_error' / 'ai_detection' / 'system' / 'tank_low'
  severity        TEXT NOT NULL,                -- 'info' / 'warning' / 'critical'
  source          TEXT NOT NULL,                -- 발생 소스 ('sensor_01', 'pump_3', 'system')
  zone_id         INTEGER REFERENCES zones(id),
  message         TEXT NOT NULL,
  value_actual    REAL,                         -- 실제 측정값
  value_threshold REAL,                         -- 임계값
  occurred_at     DATETIME NOT NULL,
  acknowledged_at DATETIME,                     -- 확인 시각
  resolved_at     DATETIME,                     -- 해결 시각
  notify_channel  TEXT,                         -- 'telegram' / 'email' / 'sms'
  notify_sent     INTEGER DEFAULT 0,
  notes           TEXT,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alert_occurred ON alert_events(occurred_at);
CREATE INDEX IF NOT EXISTS idx_alert_severity ON alert_events(severity);
CREATE INDEX IF NOT EXISTS idx_alert_resolved ON alert_events(resolved_at);

CREATE TABLE IF NOT EXISTS harvest_records (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  crop_id         INTEGER NOT NULL REFERENCES crops(id),
  zone_id         INTEGER NOT NULL REFERENCES zones(id),
  harvest_date    DATE NOT NULL,
  harvest_type    TEXT NOT NULL,                -- 'primary' (주봉오리) / 'secondary' (측봉오리)
  bud_count       INTEGER,                      -- 수확 봉오리 수
  weight_g        REAL,                         -- 총 중량 (g)
  avg_weight_g    REAL,                         -- 개당 평균 중량 (g)
  grade           TEXT,                         -- 'A' / 'B' / 'C'
  quality_score   REAL,                         -- 품질 점수 (0~100)
  operator        TEXT,                         -- 수확 담당자
  days_from_plant INTEGER,                      -- 정식 후 경과일
  notes           TEXT,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS nutrient_recipes (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  recipe_name     TEXT NOT NULL,                -- '아티초크 생육기 레시피'
  growth_stage    TEXT NOT NULL,                -- 적용 생육 단계
  target_ph_min   REAL NOT NULL,                -- 목표 pH 하한
  target_ph_max   REAL NOT NULL,                -- 목표 pH 상한
  target_ec_min   REAL NOT NULL,                -- 목표 EC 하한 (mS/cm)
  target_ec_max   REAL NOT NULL,                -- 목표 EC 상한
  target_tds_min  REAL,
  target_tds_max  REAL,
  nutrient_a_ml   REAL,                         -- A액 투입량 (mL/L)
  nutrient_b_ml   REAL,                         -- B액 투입량 (mL/L)
  ph_up_ml        REAL,                         -- pH 상승제 기준량
  ph_down_ml      REAL,                         -- pH 하강제 기준량
  is_active       INTEGER DEFAULT 1,
  notes           TEXT,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS maintenance_logs (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id       INTEGER REFERENCES devices(id),
  zone_id         INTEGER REFERENCES zones(id),
  maint_type      TEXT NOT NULL,                -- 'cleaning' / 'calibration' / 'replacement' / 'inspection' / 'repair'
  maint_date      DATE NOT NULL,
  description     TEXT NOT NULL,
  parts_replaced  TEXT,                         -- 교체 부품 (JSON 배열)
  cost_krw        INTEGER,                      -- 비용 (원)
  next_maint_date DATE,                         -- 다음 점검 예정일
  operator        TEXT,
  notes           TEXT,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS system_config (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  config_key      TEXT NOT NULL UNIQUE,
  config_value    TEXT NOT NULL,
  value_type      TEXT NOT NULL,                -- 'string' / 'integer' / 'float' / 'boolean' / 'json'
  description     TEXT,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 기본 설정값(문서 예시) — 재적용 시 중복 방지
INSERT OR IGNORE INTO system_config (config_key, config_value, value_type, description, updated_at) VALUES
  ('farm_name', '아티초크 스마트팜 1호', 'string', '농장 이름', CURRENT_TIMESTAMP),
  ('kma_api_key', '', 'string', '기상청 API 키', CURRENT_TIMESTAMP),
  ('kma_station_id', '108', 'string', '기상청 관측소 ID', CURRENT_TIMESTAMP),
  ('telegram_bot_token', '', 'string', '텔레그램 알림 봇 토큰', CURRENT_TIMESTAMP),
  ('alert_temp_max', '30.0', 'float', '온도 상한 알림 기준 (℃)', CURRENT_TIMESTAMP),
  ('alert_temp_min', '10.0', 'float', '온도 하한 알림 기준 (℃)', CURRENT_TIMESTAMP),
  ('alert_ph_min', '5.5', 'float', 'pH 하한 알림 기준', CURRENT_TIMESTAMP),
  ('alert_ph_max', '8.0', 'float', 'pH 상한 알림 기준', CURRENT_TIMESTAMP),
  ('image_retention_days', '90', 'integer', '이미지 보관 기간 (일)', CURRENT_TIMESTAMP),
  ('ai_detection_interval_sec', '30', 'integer', 'AI 감지 실행 주기 (초)', CURRENT_TIMESTAMP);
