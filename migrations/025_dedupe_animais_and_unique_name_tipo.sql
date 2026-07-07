-- Migration 025: dedupe de `animais` + índice único anti-duplicados.
--
-- Regras (por decisão de produto):
--   • Chave de unicidade: (LOWER(TRIM(nome)), tipo) — coincide com a
--     chave de pesquisa usada por `get_or_create_garanhao` e pelas
--     migrations 023/024 (matching por nome+tipo, sem dono).
--   • Scope: TODOS os registos (não apenas `ativo = TRUE`). Se um
--     animal for desactivado, o nome continua reservado.
--
-- Passos:
--   1) Mapeia dup_id → canonical_id (o mais antigo por (nome_lc, tipo)).
--   2) Reapontar TODAS as FKs para o canonical.
--   3) Apagar os registos duplicados de `animais`.
--   4) Criar `UNIQUE INDEX animais_nome_tipo_uniq`.
--
-- Idempotente: se não existirem duplicados, os UPDATEs afectam 0 linhas
-- e o CREATE UNIQUE INDEX é `IF NOT EXISTS`.

CREATE TEMP TABLE _animais_dedupe_map (
    dup_id BIGINT PRIMARY KEY,
    canonical_id BIGINT NOT NULL
);

INSERT INTO _animais_dedupe_map (dup_id, canonical_id)
SELECT a.id, c.canonical_id
FROM animais a
JOIN (
    SELECT LOWER(TRIM(nome)) AS k, tipo, MIN(id) AS canonical_id
    FROM animais
    WHERE nome IS NOT NULL AND TRIM(nome) <> ''
    GROUP BY LOWER(TRIM(nome)), tipo
    HAVING COUNT(*) > 1
) c
  ON LOWER(TRIM(a.nome)) = c.k AND a.tipo = c.tipo
WHERE a.id <> c.canonical_id;

-- Reapontamento de FKs
UPDATE estoque_dono ed SET animal_id = m.canonical_id
FROM _animais_dedupe_map m
WHERE ed.animal_id = m.dup_id;

UPDATE inseminacoes i SET animal_id_egua = m.canonical_id
FROM _animais_dedupe_map m
WHERE i.animal_id_egua = m.dup_id;

UPDATE inseminacoes i SET animal_id_garanhao = m.canonical_id
FROM _animais_dedupe_map m
WHERE i.animal_id_garanhao = m.dup_id;

UPDATE estadias e SET animal_id = m.canonical_id
FROM _animais_dedupe_map m
WHERE e.animal_id = m.dup_id;

UPDATE estadias e SET animal_doador_id = m.canonical_id
FROM _animais_dedupe_map m
WHERE e.animal_doador_id = m.dup_id;

UPDATE diario_clinico d SET animal_id = m.canonical_id
FROM _animais_dedupe_map m
WHERE d.animal_id = m.dup_id;

UPDATE trabalho_diario t SET animal_id = m.canonical_id
FROM _animais_dedupe_map m
WHERE t.animal_id = m.dup_id;

UPDATE acompanhamento_inseminacao ai SET animal_id = m.canonical_id
FROM _animais_dedupe_map m
WHERE ai.animal_id = m.dup_id;

-- Apagar duplicados de `animais`
DELETE FROM animais WHERE id IN (SELECT dup_id FROM _animais_dedupe_map);

DROP TABLE _animais_dedupe_map;

-- Índice único anti-duplicados (chave: nome_lc + tipo, global).
CREATE UNIQUE INDEX IF NOT EXISTS animais_nome_tipo_uniq
    ON animais (LOWER(TRIM(nome)), tipo);
