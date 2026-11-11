-- 044: Mudar o tipo de uma entrada em aberto (ex.: égua acompanhada em casa
-- do cliente — externo — que passa a estar internada, e vice-versa). A
-- entrada é a mesma (inseminações, diagnósticos e tarefas continuam ligados);
-- fica aqui o histórico para a Faturação contar só os dias na clínica.
-- Só acrescenta.
CREATE TABLE IF NOT EXISTS estadias_mudancas (
    id SERIAL PRIMARY KEY,
    estadia_id INTEGER NOT NULL REFERENCES estadias(id) ON DELETE CASCADE,
    data DATE NOT NULL,
    de VARCHAR(10) NOT NULL,
    para VARCHAR(10) NOT NULL,
    alojamento_id INTEGER,
    utilizador VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_estadias_mudancas_estadia ON estadias_mudancas (estadia_id, data);
