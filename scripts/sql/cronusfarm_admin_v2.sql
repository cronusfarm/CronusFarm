-- CronusFarm 관리(회원·텔레그램·영농일지) v2

CREATE TABLE IF NOT EXISTS cf_member (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  display_name TEXT,
  google_sub TEXT,
  role TEXT NOT NULL DEFAULT 'member',
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cf_telegram_user (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id TEXT NOT NULL UNIQUE,
  display_name TEXT,
  member_id INTEGER,
  enabled INTEGER NOT NULL DEFAULT 1,
  notes TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (member_id) REFERENCES cf_member(id)
);

CREATE TABLE IF NOT EXISTS cf_notify_pref (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  member_id INTEGER,
  telegram_chat_id TEXT,
  mqtt_offline INTEGER NOT NULL DEFAULT 1,
  daily_news INTEGER NOT NULL DEFAULT 1,
  weather_brief INTEGER NOT NULL DEFAULT 1,
  ai_alerts INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (member_id) REFERENCES cf_member(id)
);

CREATE TABLE IF NOT EXISTS cf_farm_diary (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  member_id INTEGER,
  author_email TEXT,
  diary_date TEXT NOT NULL,
  title TEXT,
  body TEXT NOT NULL,
  crop TEXT,
  weather_note TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (member_id) REFERENCES cf_member(id)
);
CREATE INDEX IF NOT EXISTS idx_farm_diary_date ON cf_farm_diary(diary_date DESC);

CREATE TABLE IF NOT EXISTS cf_news_clip (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT,
  title TEXT NOT NULL,
  summary TEXT,
  url TEXT,
  published_at TEXT,
  tags TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_news_clip_pub ON cf_news_clip(published_at DESC);

INSERT OR IGNORE INTO schema_version (version, note) VALUES (2, 'admin v2 tables');
