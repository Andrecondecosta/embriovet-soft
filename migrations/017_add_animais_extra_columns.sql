-- 017_add_animais_extra_columns.sql
-- Adiciona colunas extra à tabela `animais` (características físicas, genealogia,
-- identificação e observações). Usa IF NOT EXISTS para ser idempotente.

ALTER TABLE animais ADD COLUMN IF NOT EXISTS pelagem        VARCHAR(50);
ALTER TABLE animais ADD COLUMN IF NOT EXISTS altura         DECIMAL(5,1);
ALTER TABLE animais ADD COLUMN IF NOT EXISTS peso           DECIMAL(6,1);
ALTER TABLE animais ADD COLUMN IF NOT EXISTS pai            VARCHAR(100);
ALTER TABLE animais ADD COLUMN IF NOT EXISTS mae            VARCHAR(100);
ALTER TABLE animais ADD COLUMN IF NOT EXISTS avo_paterno    VARCHAR(100);
ALTER TABLE animais ADD COLUMN IF NOT EXISTS avo_materno    VARCHAR(100);
ALTER TABLE animais ADD COLUMN IF NOT EXISTS chip           VARCHAR(50);
ALTER TABLE animais ADD COLUMN IF NOT EXISTS observacoes    TEXT;
ALTER TABLE animais ADD COLUMN IF NOT EXISTS is_receptora   BOOLEAN DEFAULT FALSE;
