-- 043: proprietário que é a própria clínica (sémen próprio, éguas da casa):
-- não se fatura e o seu sémen pode usar-se sem perguntar. Só acrescenta.
ALTER TABLE dono ADD COLUMN IF NOT EXISTS da_clinica BOOLEAN NOT NULL DEFAULT FALSE;
