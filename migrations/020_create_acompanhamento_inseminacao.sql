-- 020_create_acompanhamento_inseminacao.sql
-- Cria a tabela `acompanhamento_inseminacao` para registar as datas-chave
-- do processo pós-inseminação (1º diagnóstico, confirmação, 2ª confirmação,
-- parto previsto) por estadia/animal.

CREATE TABLE IF NOT EXISTS acompanhamento_inseminacao (
    id SERIAL PRIMARY KEY,
    estadia_id INTEGER NOT NULL REFERENCES estadias(id),
    animal_id  INTEGER NOT NULL REFERENCES animais(id),
    data_inseminacao DATE,
    data_1o_diagnostico DATE,
    data_confirmacao DATE,
    data_2a_confirmacao DATE,
    data_parto_previsto DATE,
    resultado VARCHAR(30) DEFAULT 'pendente',
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT acompanhamento_inseminacao_estadia_unique UNIQUE (estadia_id)
);

CREATE INDEX IF NOT EXISTS idx_acomp_insem_animal_id  ON acompanhamento_inseminacao(animal_id);
CREATE INDEX IF NOT EXISTS idx_acomp_insem_estadia_id ON acompanhamento_inseminacao(estadia_id);
