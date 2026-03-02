ALTER TABLE app_settings
ADD COLUMN IF NOT EXISTS welcome_completed BOOLEAN DEFAULT FALSE;

UPDATE app_settings
SET welcome_completed = FALSE
WHERE welcome_completed IS NULL;