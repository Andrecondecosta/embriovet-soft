ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS logo_base64 TEXT;
ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS company_name TEXT;
ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS primary_color TEXT;
ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'pt-PT';

UPDATE app_settings
SET language = 'pt-PT'
WHERE language IS NULL;