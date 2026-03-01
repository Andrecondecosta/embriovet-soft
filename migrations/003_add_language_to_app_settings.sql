ALTER TABLE app_settings
ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'pt-PT';

UPDATE app_settings
SET language = 'pt-PT'
WHERE language IS NULL;