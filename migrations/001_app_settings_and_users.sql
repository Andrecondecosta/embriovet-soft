-- APP SETTINGS (white-label + onboarding)
CREATE TABLE IF NOT EXISTS app_settings (
  id SERIAL PRIMARY KEY,
  company_name TEXT,
  logo_base64 TEXT,
  primary_color TEXT,
  is_initialized BOOLEAN DEFAULT FALSE,
  show_initial_credentials BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- garantir 1 row
INSERT INTO app_settings (company_name)
SELECT 'Sistema'
WHERE NOT EXISTS (SELECT 1 FROM app_settings);

-- usuarios: must_change_password
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='usuarios'
  ) THEN
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_name='usuarios' AND column_name='must_change_password'
    ) THEN
      ALTER TABLE usuarios ADD COLUMN must_change_password BOOLEAN DEFAULT FALSE;
    END IF;

    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_name='usuarios' AND column_name='created_at'
    ) THEN
      ALTER TABLE usuarios ADD COLUMN created_at TIMESTAMPTZ DEFAULT now();
    END IF;

    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_name='usuarios' AND column_name='updated_at'
    ) THEN
      ALTER TABLE usuarios ADD COLUMN updated_at TIMESTAMPTZ DEFAULT now();
    END IF;
  END IF;
END $$;