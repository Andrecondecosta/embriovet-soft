-- 044: a faturação passa a ter também as palhetas de sémen de clientes
-- usadas em inseminações ("recebidas" pelo dono da égua, "gastas" para o
-- dono do sémen). Só alarga a regra do tipo.
ALTER TABLE faturacao_linhas DROP CONSTRAINT IF EXISTS faturacao_linhas_tipo_check;
ALTER TABLE faturacao_linhas ADD CONSTRAINT faturacao_linhas_tipo_check
    CHECK (tipo IN ('estadia', 'armazenamento', 'palhetas_recebidas', 'palhetas_gastas'));
