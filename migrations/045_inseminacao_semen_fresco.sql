-- 045: Inseminação com sémen fresco (só o nome do garanhão; não gasta
-- palhetas do stock). Segue os mesmos passos que a do congelado (D+1, DG).
-- Só acrescenta.
ALTER TABLE inseminacoes ADD COLUMN IF NOT EXISTS fresco BOOLEAN NOT NULL DEFAULT FALSE;
