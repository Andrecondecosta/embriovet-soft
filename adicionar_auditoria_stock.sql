-- Adicionar campos de auditoria à tabela estoque_dono
-- Execute este script no seu banco de dados PostgreSQL

ALTER TABLE estoque_dono 
ADD COLUMN IF NOT EXISTS data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN IF NOT EXISTS criado_por VARCHAR(100);

-- Atualizar registros existentes com data atual (opcional)
UPDATE estoque_dono 
SET data_criacao = CURRENT_TIMESTAMP 
WHERE data_criacao IS NULL;

-- Comentário
COMMENT ON COLUMN estoque_dono.data_criacao IS 'Data e hora em que o stock foi criado';
COMMENT ON COLUMN estoque_dono.criado_por IS 'Utilizador que criou o stock';
