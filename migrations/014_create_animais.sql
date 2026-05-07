-- 014_create_animais.sql
-- Cria a tabela `animais` para gestão de éguas, garanhões e receptoras.

CREATE TABLE IF NOT EXISTS animais (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('egua', 'garanhao', 'receptora')),
    raca VARCHAR(100),
    data_nascimento DATE,
    numero_registo VARCHAR(50),
    dono_id INTEGER REFERENCES dono(id),
    foto_base64 TEXT,
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_animais_tipo ON animais(tipo);
CREATE INDEX IF NOT EXISTS idx_animais_dono_id ON animais(dono_id);
CREATE INDEX IF NOT EXISTS idx_animais_ativo ON animais(ativo);
