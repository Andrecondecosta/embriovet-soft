-- Migration 026: normalização de nomes de garanhão + unaccent.
--
-- Contexto: `get_or_create_garanhao` faz matching por
-- `LOWER(TRIM(nome))`, mas isso trata "Falcao" e "Falcão" como nomes
-- distintos, criando duplicados que a UNIQUE INDEX 025 não consegue
-- detectar. Instalar `unaccent` e alterar o índice único para
-- `LOWER(unaccent(TRIM(nome)))` resolve o problema.
--
-- `unaccent` NÃO é IMMUTABLE por defeito (depende do dicionário), o que
-- impede o seu uso directo num expression index. Usamos um wrapper
-- IMMUTABLE (`f_unaccent`) — padrão bem documentado do PostgreSQL.
--
-- Idempotente: usa `IF NOT EXISTS` e `DROP INDEX IF EXISTS`.

CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE OR REPLACE FUNCTION f_unaccent(text)
RETURNS text
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
AS $$
    SELECT public.unaccent('public.unaccent'::regdictionary, $1)
$$;

-- Reconstrói o índice único com f_unaccent + colapso de espaços internos.
DROP INDEX IF EXISTS animais_nome_tipo_uniq;

CREATE UNIQUE INDEX animais_nome_tipo_uniq
    ON animais (
        LOWER(f_unaccent(TRIM(REGEXP_REPLACE(nome, '\s+', ' ', 'g')))),
        tipo
    );
