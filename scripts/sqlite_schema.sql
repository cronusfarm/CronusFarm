-- CronusFarm: 관계형 메타·작물·카메라 메타 (SQLite)
-- 시계열(외기/내부 RS485/액추에이터 duty/카메라 이벤트 수치)은 InfluxDB 1.x DB `cronusfarm` 사용.
--
-- Influx measurement 요약 (시드·런타임 공통 권장 태그/필드):
--   external_weather,location=seoul,source=open_meteo_archive
--     temp_c, rh_pct, rain_mm, wind_speed_ms, wind_gust_ms, wind_dir_deg, wind_run_km
--   internal_rs485,device=3178,metric=ec|tds|cf|ph|orp|temp|hum  value=
--   actuator,key=led_a1|...  value=0|1   (기존 MQTT 플로우와 동일)
--   actuator_duty,key=led_a1|...  on_sec=, off_sec=  (해당 시각 구간 누적 ON/OFF 초)
--   camera_event,bed_code=A|B|C|..., camera_id=main  path=, duration_sec=, size_mb=

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS bed (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bed_layer (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bed_id INTEGER NOT NULL REFERENCES bed(id) ON DELETE CASCADE,
  layer_no INTEGER NOT NULL,
  label TEXT NOT NULL,
  UNIQUE (bed_id, layer_no)
);

CREATE TABLE IF NOT EXISTS crop_assignment (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bed_layer_id INTEGER NOT NULL REFERENCES bed_layer(id) ON DELETE CASCADE,
  species TEXT NOT NULL,
  variety TEXT,
  planted_date TEXT,
  expected_harvest TEXT,
  notes TEXT
);

-- 시간별 외기(시드·백업용; Grafana는 Influx external_weather 조회 권장)
CREATE TABLE IF NOT EXISTS weather_obs_hourly (
  obs_time TEXT NOT NULL PRIMARY KEY,
  temp_c REAL,
  rh_pct REAL,
  rain_mm REAL,
  wind_speed_ms REAL,
  wind_gust_ms REAL,
  wind_dir_deg REAL,
  wind_run_km REAL,
  source TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS camera_recording (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bed_code TEXT,
  layer_no INTEGER,
  file_path TEXT NOT NULL,
  started_at TEXT NOT NULL,
  duration_sec INTEGER,
  size_mb REAL,
  notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_bed_layer_bed ON bed_layer(bed_id);
CREATE INDEX IF NOT EXISTS idx_crop_layer ON crop_assignment(bed_layer_id);
CREATE INDEX IF NOT EXISTS idx_camera_started ON camera_recording(started_at);
