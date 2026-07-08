-- Migration 029: uma égua só pode ter UMA estadia aberta em simultâneo.
--
-- Regra: a chave real do "onde está esta égua agora" é (animal_id) —
-- se `data_saida IS NULL`, essa linha representa a estadia activa.
-- Ter duas linhas assim para o mesmo animal é sempre um erro
-- (aconteceu com a égua Matilde em produção — ver iteration_32).
--
-- Impomos com um UNIQUE INDEX PARCIAL, que aceita muitas estadias
-- fechadas (`data_saida NOT NULL`) mas rejeita a criação de uma
-- segunda em aberto.
--
-- Pré-requisito: NÃO devem existir duplicados no momento em que esta
-- migration corre. O runtime já se encarrega de fundir a Matilde
-- (feito manualmente) e a validação nas funções `_criar_estadia_apenas`
-- e `_criar_animal_e_estadia` previne novos duplicados.
--
-- Idempotente via `IF NOT EXISTS`.

CREATE UNIQUE INDEX IF NOT EXISTS estadias_uma_aberta_por_animal
    ON estadias (animal_id)
    WHERE data_saida IS NULL;
