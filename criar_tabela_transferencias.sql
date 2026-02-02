-- ================================================
-- SCRIPT PARA ADICIONAR TABELA DE TRANSFERÊNCIAS
-- Execute este script no PostgreSQL para adicionar
-- a funcionalidade de rastreamento de transferências
-- ================================================

-- Criar tabela de transferências
CREATE TABLE IF NOT EXISTS transferencias (
    id SERIAL PRIMARY KEY,
    estoque_id INTEGER REFERENCES estoque_dono(id) ON DELETE SET NULL,
    proprietario_origem_id INTEGER REFERENCES dono(id) ON DELETE SET NULL,
    proprietario_destino_id INTEGER REFERENCES dono(id) ON DELETE SET NULL,
    quantidade INTEGER NOT NULL,
    data_transferencia TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_quantidade_positiva CHECK (quantidade > 0)
);

COMMENT ON TABLE transferencias IS 'Histórico de transferências de palhetas entre proprietários';
COMMENT ON COLUMN transferencias.estoque_id IS 'Lote de estoque de origem';
COMMENT ON COLUMN transferencias.proprietario_origem_id IS 'Proprietário que cedeu as palhetas';
COMMENT ON COLUMN transferencias.proprietario_destino_id IS 'Proprietário que recebeu as palhetas';
COMMENT ON COLUMN transferencias.quantidade IS 'Quantidade de palhetas transferidas';
COMMENT ON COLUMN transferencias.data_transferencia IS 'Data e hora da transferência';

-- Criar índices para melhorar performance
CREATE INDEX IF NOT EXISTS idx_transferencias_origem ON transferencias(proprietario_origem_id);
CREATE INDEX IF NOT EXISTS idx_transferencias_destino ON transferencias(proprietario_destino_id);
CREATE INDEX IF NOT EXISTS idx_transferencias_data ON transferencias(data_transferencia);
CREATE INDEX IF NOT EXISTS idx_transferencias_estoque ON transferencias(estoque_id);

-- Verificar se a tabela foi criada
SELECT 'Tabela de transferências criada com sucesso!' as status;

-- Mostrar estrutura da tabela
\d transferencias
