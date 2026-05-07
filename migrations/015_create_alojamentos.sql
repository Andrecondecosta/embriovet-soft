-- 015_create_alojamentos.sql
-- Cria a tabela `alojamentos` para gestão de boxes, paddocks e outros locais.

CREATE TABLE IF NOT EXISTS alojamentos (
    id SERIAL PRIMARY KEY,
    tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('box', 'paddock', 'outro')),
    nome VARCHAR(50) NOT NULL,
    capacidade INTEGER DEFAULT 1,
    ativo BOOLEAN DEFAULT TRUE,
    observacoes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alojamentos_tipo ON alojamentos(tipo);
CREATE INDEX IF NOT EXISTS idx_alojamentos_ativo ON alojamentos(ativo);
