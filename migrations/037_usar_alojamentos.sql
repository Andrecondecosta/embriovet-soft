-- 037: opção para clínicas que não usam boxes/paddocks nas estadias.
-- Só acrescenta (por omissão TRUE: tudo como antes).
ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS usar_alojamentos BOOLEAN NOT NULL DEFAULT TRUE;
