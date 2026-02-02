-- ================================================
-- SCRIPT PARA CORRIGIR TABELA DE TRANSFERÊNCIAS
-- Execute este script para corrigir a estrutura
-- ================================================

-- Opção 1: Recriar a tabela do zero (RECOMENDADO se não tiver dados importantes)
DROP TABLE IF EXISTS transferencias CASCADE;

CREATE TABLE transferencias (
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
CREATE INDEX idx_transferencias_origem ON transferencias(proprietario_origem_id);
CREATE INDEX idx_transferencias_destino ON transferencias(proprietario_destino_id);
CREATE INDEX idx_transferencias_data ON transferencias(data_transferencia);
CREATE INDEX idx_transferencias_estoque ON transferencias(estoque_id);

-- Verificar estrutura
\d transferencias

-- Mensagem de sucesso
SELECT '✅ Tabela de transferências corrigida com sucesso!' as status;
