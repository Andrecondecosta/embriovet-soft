-- ============================================================
-- Migration 032 — registo_clinico (novo "Registo de hoje" das éguas)
-- ============================================================
-- O registo passa a ser por parte do aparelho reprodutor — ovário
-- esquerdo/direito (vários folículos, achados), útero (edema, líquido),
-- cérvix — mais diagnóstico de gestação e tratamento. Os campos ainda
-- vão afinando com o uso, por isso o conteúdo fica em JSONB (`dados`).
--
-- A tabela antiga `diario_clinico` mantém-se tal como está: os registos
-- antigos continuam a aparecer no histórico da ficha. Só aditivo.
--
-- `opcoes_clinicas`: valores escritos à mão no tratamento ("outro"
-- antibiótico, outras infusões…) ficam guardados para a próxima vez.
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS registo_clinico (
    id            SERIAL PRIMARY KEY,
    animal_id     INTEGER NOT NULL REFERENCES animais(id) ON DELETE CASCADE,
    estadia_id    INTEGER REFERENCES estadias(id) ON DELETE SET NULL,
    data_registo  TIMESTAMP NOT NULL,
    dados         JSONB NOT NULL DEFAULT '{}'::jsonb,
    prioritario   BOOLEAN NOT NULL DEFAULT FALSE,
    utilizador    VARCHAR(50),
    created_at    TIMESTAMP DEFAULT NOW(),
    updated_at    TIMESTAMP
);

CREATE INDEX IF NOT EXISTS registo_clinico_animal_data_idx
    ON registo_clinico (animal_id, data_registo DESC);

CREATE TABLE IF NOT EXISTS opcoes_clinicas (
    id          SERIAL PRIMARY KEY,
    categoria   VARCHAR(30) NOT NULL,
    valor       VARCHAR(80) NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS opcoes_clinicas_categoria_valor_idx
    ON opcoes_clinicas (categoria, LOWER(valor));

COMMIT;
