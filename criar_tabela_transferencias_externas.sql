-- ================================================
-- ADICIONAR TABELA DE TRANSFERÊNCIAS EXTERNAS
-- (Vendas/Envios para fora do sistema)
-- ================================================

CREATE TABLE IF NOT EXISTS transferencias_externas (
    id SERIAL PRIMARY KEY,
    estoque_id INTEGER REFERENCES estoque_dono(id) ON DELETE SET NULL,
    proprietario_origem_id INTEGER REFERENCES dono(id) ON DELETE SET NULL,
    garanhao VARCHAR(255) NOT NULL,
    destinatario_externo VARCHAR(255) NOT NULL,
    quantidade INTEGER NOT NULL,
    tipo VARCHAR(50) DEFAULT 'Venda',
    observacoes TEXT,
    data_transferencia TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_quantidade_positiva_ext CHECK (quantidade > 0)
);

COMMENT ON TABLE transferencias_externas IS 'Histórico de vendas e transferências para fora do sistema';
COMMENT ON COLUMN transferencias_externas.estoque_id IS 'Lote de estoque de origem';
COMMENT ON COLUMN transferencias_externas.proprietario_origem_id IS 'Proprietário que vendeu/enviou';
COMMENT ON COLUMN transferencias_externas.garanhao IS 'Nome do garanhão';
COMMENT ON COLUMN transferencias_externas.destinatario_externo IS 'Nome do comprador/destinatário externo';
COMMENT ON COLUMN transferencias_externas.quantidade IS 'Quantidade de palhetas vendidas/enviadas';
COMMENT ON COLUMN transferencias_externas.tipo IS 'Tipo: Venda, Doação, Exportação, etc';
COMMENT ON COLUMN transferencias_externas.observacoes IS 'Observações adicionais';
COMMENT ON COLUMN transferencias_externas.data_transferencia IS 'Data e hora da operação';

-- Criar índices
CREATE INDEX IF NOT EXISTS idx_transf_ext_proprietario ON transferencias_externas(proprietario_origem_id);
CREATE INDEX IF NOT EXISTS idx_transf_ext_data ON transferencias_externas(data_transferencia);
CREATE INDEX IF NOT EXISTS idx_transf_ext_garanhao ON transferencias_externas(garanhao);
CREATE INDEX IF NOT EXISTS idx_transf_ext_destinatario ON transferencias_externas(destinatario_externo);

-- Verificar
\d transferencias_externas

SELECT '✅ Tabela de transferências externas criada com sucesso!' as status;
