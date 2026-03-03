ALTER TABLE estoque_dono
ADD COLUMN IF NOT EXISTS cor TEXT;

ALTER TABLE estoque_dono
DROP CONSTRAINT IF EXISTS check_qualidade_valida;

ALTER TABLE estoque_dono
ALTER COLUMN qualidade TYPE TEXT USING qualidade::TEXT;