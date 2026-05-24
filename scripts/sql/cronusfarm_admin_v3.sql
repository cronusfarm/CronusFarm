-- CronusFarm 관리 v3: Google 로그인 추적·텔레그램 신청 상태

ALTER TABLE cf_member ADD COLUMN google_sub TEXT;
ALTER TABLE cf_member ADD COLUMN last_login_at TEXT;

ALTER TABLE cf_telegram_user ADD COLUMN status TEXT NOT NULL DEFAULT 'approved';
ALTER TABLE cf_telegram_user ADD COLUMN applied_at TEXT;
ALTER TABLE cf_telegram_user ADD COLUMN telegram_username TEXT;

CREATE INDEX IF NOT EXISTS idx_cf_member_active ON cf_member(active);
CREATE INDEX IF NOT EXISTS idx_cf_tg_user_status ON cf_telegram_user(status);

INSERT OR IGNORE INTO schema_version (version, note) VALUES (3, 'admin v3 member login + telegram apply');
