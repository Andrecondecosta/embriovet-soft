-- Tabela de auditoria para rastrear edições de transferências e inseminações
CREATE TABLE IF NOT EXISTS historico_edicoes (
    id SERIAL PRIMARY KEY,
    tabela_nome VARCHAR(100) NOT NULL,
    record_id INTEGER NOT NULL,
    dados_antigos JSONB,
    dados_novos JSONB,
    utilizador_nome VARCHAR(255) DEFAULT '—',
    data_alteracao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_historico_tabela_record ON historico_edicoes(tabela_nome, record_id);
