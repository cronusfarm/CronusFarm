-- CronusFarm 기록 DB 스키마 v1 (SQLite)
-- 적용: python scripts/init_cronusfarm_sqlite.py 또는 sqlite3 < 파일

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL DEFAULT (datetime('now')),
  note TEXT
);

CREATE TABLE IF NOT EXISTS device (
  device_id TEXT PRIMARY KEY,
  label TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tele_sample (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL,
  ts_ms INTEGER NOT NULL,
  topic TEXT,
  raw TEXT NOT NULL,
  FOREIGN KEY (device_id) REFERENCES device(device_id)
);
CREATE INDEX IF NOT EXISTS idx_tele_sample_dev_ts ON tele_sample(device_id, ts_ms DESC);

CREATE TABLE IF NOT EXISTS tele_channel_fact (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL,
  ts_ms INTEGER NOT NULL,
  channel_key TEXT NOT NULL,
  state INTEGER,
  auto_mode INTEGER,
  on_sec INTEGER,
  off_sec INTEGER,
  FOREIGN KEY (device_id) REFERENCES device(device_id)
);
CREATE INDEX IF NOT EXISTS idx_tcf_dev_ch_ts ON tele_channel_fact(device_id, channel_key, ts_ms DESC);

CREATE TABLE IF NOT EXISTS mqtt_cmd_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL,
  ts_ms INTEGER NOT NULL,
  topic TEXT,
  payload TEXT NOT NULL,
  FOREIGN KEY (device_id) REFERENCES device(device_id)
);
CREATE INDEX IF NOT EXISTS idx_cmd_dev_ts ON mqtt_cmd_log(device_id, ts_ms DESC);

CREATE TABLE IF NOT EXISTS mqtt_status_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL,
  ts_ms INTEGER NOT NULL,
  topic TEXT,
  payload TEXT,
  FOREIGN KEY (device_id) REFERENCES device(device_id)
);
CREATE INDEX IF NOT EXISTS idx_status_dev_ts ON mqtt_status_log(device_id, ts_ms DESC);

CREATE TABLE IF NOT EXISTS pump_guard_event (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL,
  ts_ms INTEGER NOT NULL,
  channel_key TEXT NOT NULL,
  code TEXT NOT NULL,
  remain_sec INTEGER,
  raw_token TEXT,
  FOREIGN KEY (device_id) REFERENCES device(device_id)
);
CREATE INDEX IF NOT EXISTS idx_guard_dev_ts ON pump_guard_event(device_id, ts_ms DESC);

CREATE TABLE IF NOT EXISTS settings_kv (
  device_id TEXT NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (device_id, key),
  FOREIGN KEY (device_id) REFERENCES device(device_id)
);

CREATE TABLE IF NOT EXISTS manual_switch_event (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL,
  ts_ms INTEGER NOT NULL,
  channel_key TEXT NOT NULL,
  source TEXT,
  prev_auto INTEGER,
  new_auto INTEGER,
  prev_state INTEGER,
  new_state INTEGER,
  meta_json TEXT,
  FOREIGN KEY (device_id) REFERENCES device(device_id)
);
CREATE INDEX IF NOT EXISTS idx_manual_dev_ts ON manual_switch_event(device_id, ts_ms DESC);

CREATE TABLE IF NOT EXISTS schedule_profile (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL,
  name TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (device_id) REFERENCES device(device_id)
);

CREATE TABLE IF NOT EXISTS alert_rule (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL,
  name TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (device_id) REFERENCES device(device_id)
);

CREATE TABLE IF NOT EXISTS sensor_reading (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL,
  ts_ms INTEGER NOT NULL,
  zone TEXT,
  ph REAL,
  ec REAL,
  temp_c REAL,
  humidity_pct REAL,
  light_lux REAL,
  co2_ppm REAL,
  source TEXT,
  raw_json TEXT,
  FOREIGN KEY (device_id) REFERENCES device(device_id)
);
CREATE INDEX IF NOT EXISTS idx_sensor_dev_ts ON sensor_reading(device_id, ts_ms DESC);

-- 채널별: 시간대(window, on_min/off_min=하루 내 분) 또는 주기(cycle, on_sec/off_sec=반복 초).
CREATE TABLE IF NOT EXISTS schedule_rule (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL,
  channel_key TEXT NOT NULL,
  dow_mask INTEGER NOT NULL DEFAULT 127,
  slot_index INTEGER NOT NULL DEFAULT 0,
  on_min INTEGER NOT NULL DEFAULT 0,
  off_min INTEGER NOT NULL DEFAULT 0,
  enabled INTEGER NOT NULL DEFAULT 1,
  rule_kind TEXT NOT NULL DEFAULT 'window',
  on_sec INTEGER,
  off_sec INTEGER,
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (device_id) REFERENCES device(device_id)
);
CREATE INDEX IF NOT EXISTS idx_schedule_rule_dev_ch ON schedule_rule(device_id, channel_key);

-- CCTV 사진: 원본 파일은 파일시스템에 저장하고, DB에는 메타데이터/경로만 저장한다.
-- 기본 경로(권장): ~/CronusFarm/CCTV/cam01/YYYY/MM/DD/YYYYMMDD_HHMMSS.jpg
CREATE TABLE IF NOT EXISTS cctv_photo (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL,
  camera_key TEXT NOT NULL,         -- 예: cam01, cam02 ...
  captured_at_ms INTEGER NOT NULL,  -- epoch ms
  rel_path TEXT NOT NULL,           -- base_dir 기준 상대경로
  bytes INTEGER,
  sha256 TEXT,
  width INTEGER,
  height INTEGER,
  meta_json TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (device_id) REFERENCES device(device_id)
);
CREATE INDEX IF NOT EXISTS idx_cctv_photo_dev_cam_ts ON cctv_photo(device_id, camera_key, captured_at_ms DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_cctv_photo_rel_path ON cctv_photo(rel_path);

INSERT OR IGNORE INTO schema_version (version, note) VALUES (1, 'cronusfarm_record_v1 initial');
INSERT OR IGNORE INTO schema_version (version, note) VALUES (2, 'schedule_rule for NRDB2');
INSERT OR IGNORE INTO schema_version (version, note) VALUES (3, 'schedule_rule rule_kind + cycle on_sec/off_sec');
INSERT OR IGNORE INTO schema_version (version, note) VALUES (4, 'cctv_photo table (file path + metadata)');
INSERT OR IGNORE INTO schema_version (version, note) VALUES (5, 'GET /api/channel/timeline|status, POST /ingest/manual_event (브리지 런타임)');
