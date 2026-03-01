ALTER TABLE app_settings
ADD COLUMN IF NOT EXISTS theme_key TEXT DEFAULT 'blue';

UPDATE app_settings
SET theme_key = 'blue'
WHERE theme_key IS NULL;